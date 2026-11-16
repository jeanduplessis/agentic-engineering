"""Offline tests for review_payload.py. Run: python3 -m unittest discover -s skills/review-for-me/scripts -v"""
from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_payload as rp  # noqa: E402

HEAD = "4f26417b6e0ec96c32715b6857cb333fb30b80fc"
OTHER_HEAD = "a" * 40

# RIGHT lines: hunk 1 = 1-5, hunk 2 = 21-23. LEFT lines: hunk 1 = 1-4, hunk 2 = 20-22.
PATCH = "\n".join(
    [
        "@@ -1,4 +1,5 @@",
        " line1",
        "-old2",
        "+new2",
        "+new3",
        " line3",
        " line4",
        "@@ -20,3 +21,3 @@",
        " ctx20",
        "-old21",
        "+new22",
        " ctx22",
        "\\ No newline at end of file",
    ]
)


class FakeGitHub:
    """Stands in for `gh api`; echoes posted comments back unless told otherwise."""

    def __init__(self, *, login="reviewer", author="author", head=HEAD, files=None, echo_comments=True):
        self._login = login
        self._author = author
        self._head = head
        self._files = files if files is not None else {"src/app.py": PATCH, "docs/guide.md": PATCH}
        self._echo = echo_comments
        self.created = []

    def login(self):
        return self._login

    def pull(self, repo, pr):
        return {"head_sha": self._head, "state": "open", "merged": False, "author": self._author, "url": "https://example.test/pr"}

    def files(self, repo, pr):
        return dict(self._files)

    def create_review(self, repo, pr, payload):
        self.created.append(copy.deepcopy(payload))
        return {"id": 99, "html_url": "https://example.test/review/99", "state": "COMMENTED", "body": payload["body"]}

    def review_comments(self, repo, pr, review_id):
        if not self._echo:
            return []
        return [
            {"path": c["path"], "line": c["line"], "side": c["side"], "start_line": c.get("start_line")}
            for c in self.created[-1]["comments"]
        ]


def make_draft(**overrides):
    draft = {
        "repo": "acme/widgets",
        "pr": 7,
        "commit_id": HEAD,
        "model": "Claude Opus 5.5",
        "summary": "I checked the release notes and they match.",
        "comments": [
            {"path": "docs/guide.md", "line": 22, "body": "Is this link meant to point at v2?"},
            {"path": "src/app.py", "line": 3, "body": "Would `>=` be closer to the intent here?"},
            {"path": "docs/guide.md", "start_line": 2, "line": 4, "body": "Nit: should this list be sorted?"},
        ],
    }
    draft.update(overrides)
    return draft


def approved_digest(rendered):
    last = rendered.strip().splitlines()[-1]
    assert last.startswith("Digest: "), last
    return last[len("Digest: "):]


class ReviewPayloadTests(unittest.TestCase):
    def run_cli(self, draft, *args, gh):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "draft.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(draft, handle)
            out, err = io.StringIO(), io.StringIO()
            code = rp.main([args[0], path, *args[1:]], gh=gh, out=out, err=err)
            return code, out.getvalue(), err.getvalue()

    def test_render_then_post_submits_exactly_the_approved_review(self):
        gh = FakeGitHub()
        draft = make_draft()

        code, rendered, _ = self.run_cli(draft, "render", gh=gh)
        self.assertEqual(code, 0)
        disclosure = (
            "> [!NOTE]\n"
            "> _This review was written by Claude Opus 5.5 on behalf of @reviewer, "
            "and posted after he reviewed and approved it._"
        )
        self.assertIn(disclosure + "\n\nI checked the release notes", rendered)
        # Grouped by file in first-appearance order, then by line, numbered in posting order.
        self.assertLess(rendered.index("**1. Lines 2-4**"), rendered.index("**2. Line 22**"))
        self.assertLess(rendered.index("**2. Line 22**"), rendered.index("## `src/app.py`"))
        self.assertIn("**3. Line 3**", rendered)
        approved = approved_digest(rendered)

        code, out, err = self.run_cli(draft, "post", "--event", "REQUEST_CHANGES", "--digest", approved, gh=gh)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(gh.created), 1)
        posted = gh.created[0]
        self.assertEqual(posted["event"], "REQUEST_CHANGES")
        self.assertEqual(posted["commit_id"], HEAD)
        self.assertTrue(posted["body"].startswith(disclosure))
        self.assertEqual(
            [(c["path"], c["line"], c.get("start_line")) for c in posted["comments"]],
            [("docs/guide.md", 4, 2), ("docs/guide.md", 22, None), ("src/app.py", 3, None)],
        )
        self.assertIn("verified", out)

    def test_post_refuses_a_draft_edited_after_approval(self):
        gh = FakeGitHub()
        draft = make_draft()
        _, rendered, _ = self.run_cli(draft, "render", gh=gh)
        approved = approved_digest(rendered)

        draft["comments"][1]["body"] = "This is wrong."
        code, _, err = self.run_cli(draft, "post", "--event", "COMMENT", "--digest", approved, gh=gh)

        self.assertEqual(code, 1)
        self.assertIn(approved, err)
        self.assertEqual(gh.created, [])

    def test_check_and_post_stop_when_the_pr_head_moved(self):
        gh = FakeGitHub(head=OTHER_HEAD)

        code, _, err = self.run_cli(make_draft(), "check", gh=gh)
        self.assertEqual(code, 1)
        self.assertIn(HEAD[:7], err)
        self.assertIn(OTHER_HEAD[:7], err)

        code, _, _ = self.run_cli(make_draft(), "post", "--event", "COMMENT", "--digest", "000000000000", gh=gh)
        self.assertEqual(code, 1)
        self.assertEqual(gh.created, [])

    def test_check_accepts_only_lines_inside_diff_hunks(self):
        gh = FakeGitHub(files={"src/app.py": PATCH, "logo.png": None})
        valid = [
            {"path": "src/app.py", "line": 23, "body": "context line in hunk 2"},
            {"path": "src/app.py", "line": 2, "side": "LEFT", "body": "removed line"},
            {"path": "src/app.py", "start_line": 21, "line": 22, "body": "range inside hunk 2"},
        ]
        code, out, _ = self.run_cli(make_draft(comments=valid), "check", gh=gh)
        self.assertEqual(code, 0)
        self.assertIn("OK: 3 comments", out)

        invalid = [
            {"path": "src/app.py", "line": 10, "body": "between hunks"},
            {"path": "src/app.py", "line": 5, "side": "LEFT", "body": "past the left side of hunk 1"},
            {"path": "src/app.py", "start_line": 4, "line": 22, "body": "spans two hunks"},
            {"path": "README.md", "line": 1, "body": "file not in the PR"},
            {"path": "logo.png", "line": 1, "body": "binary file"},
        ]
        code, _, err = self.run_cli(make_draft(comments=invalid), "check", gh=gh)
        self.assertEqual(code, 1)
        for location in ("src/app.py:10)", "src/app.py:5)", "src/app.py:22)", "README.md:1)", "logo.png:1)"):
            self.assertIn(location, err)

    def test_own_pr_can_only_be_posted_as_a_comment(self):
        gh = FakeGitHub(login="jdoe", author="JDoe")
        draft = make_draft()
        _, rendered, _ = self.run_cli(draft, "render", gh=gh)
        approved = approved_digest(rendered)

        code, _, err = self.run_cli(draft, "post", "--event", "APPROVE", "--digest", approved, gh=gh)
        self.assertEqual(code, 1)
        self.assertIn("COMMENT", err)
        self.assertEqual(gh.created, [])

        code, _, _ = self.run_cli(draft, "post", "--event", "COMMENT", "--digest", approved, gh=gh)
        self.assertEqual(code, 0)
        self.assertEqual([p["event"] for p in gh.created], ["COMMENT"])

    def test_check_reports_every_malformed_field(self):
        draft = make_draft(
            commit_id="4f26417",
            model="[model]",
            summary="> [!NOTE]\n> already disclosed",
            comments=[
                {"path": "src/app.py", "line": 3, "body": "one"},
                {"path": "src/app.py", "line": 3, "body": "two"},
                {"path": "src/app.py", "start_line": 5, "line": 3, "body": "backwards range"},
            ],
        )
        code, _, err = self.run_cli(draft, "check", gh=FakeGitHub())
        self.assertEqual(code, 1)
        for field in ('"commit_id"', '"model"', '"summary"', "src/app.py:3 (RIGHT)", '"start_line"'):
            self.assertIn(field, err)

    def test_post_reports_comments_github_did_not_keep(self):
        gh = FakeGitHub(echo_comments=False)
        draft = make_draft()
        _, rendered, _ = self.run_cli(draft, "render", gh=gh)
        approved = approved_digest(rendered)

        code, out, _ = self.run_cli(draft, "post", "--event", "COMMENT", "--digest", approved, gh=gh)

        self.assertEqual(code, 1)
        self.assertEqual(len(gh.created), 1)
        self.assertIn("missing comment at src/app.py:3", out)

    def test_parse_patch_numbers_both_sides_of_each_hunk(self):
        hunks = rp.parse_patch(PATCH)
        self.assertEqual(
            hunks,
            [
                {"LEFT": {1, 2, 3, 4}, "RIGHT": {1, 2, 3, 4, 5}},
                {"LEFT": {20, 21, 22}, "RIGHT": {21, 22, 23}},
            ],
        )


if __name__ == "__main__":
    unittest.main()

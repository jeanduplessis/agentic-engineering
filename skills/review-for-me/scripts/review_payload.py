#!/usr/bin/env python3
"""Check, render, and post a GitHub pull-request review drafted for a user.

Subcommands:

  check  DRAFT                                read-only validation against the live PR
  render DRAFT                                validate, then print the exact review and its digest
  post   DRAFT --event EVENT --digest DIGEST  re-validate, post one review, verify every anchor

DRAFT is a JSON file:

  {
    "repo": "owner/name",
    "pr": 123,
    "commit_id": "<full head SHA the review was done against>",
    "model": "<name of the model writing the review>",
    "summary": "<review body in Markdown, without the disclosure>",
    "comments": [
      {"path": "src/app.py", "line": 42, "body": "..."},
      {"path": "src/app.py", "start_line": 40, "line": 42, "side": "RIGHT", "body": "..."}
    ]
  }

The script prepends the disclosure to the summary. Requires Python 3.8+ and an
authenticated GitHub CLI (`gh`). Exit codes: 0 success, 1 refused or failed, 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, TextIO, Tuple

EVENTS = ("COMMENT", "REQUEST_CHANGES", "APPROVE")
SIDES = ("RIGHT", "LEFT")
DISCLOSURE = (
    "> [!NOTE]\n"
    "> _This review was written by {model} on behalf of @{login}, "
    "and posted after he reviewed and approved it._"
)
PLACEHOLDER_MODELS = {"", "model", "[model]", "<model>", "{model}"}
COMMENT_KEYS = {"path", "line", "start_line", "side", "start_side", "body"}
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")

Draft = Dict[str, Any]
Payload = Dict[str, Any]


class DraftError(Exception):
    """The draft or the live PR state does not allow the requested action."""


# --------------------------------------------------------------------------- pure logic


def parse_patch(patch: str) -> List[Dict[str, Set[int]]]:
    """Return the commentable line numbers, per side, of each hunk in a unified-diff patch."""
    hunks: List[Dict[str, Set[int]]] = []
    current: Optional[Dict[str, Set[int]]] = None
    left = right = 0
    for raw in patch.splitlines():
        match = HUNK_RE.match(raw)
        if match:
            left, right = int(match.group(1)), int(match.group(2))
            current = {"LEFT": set(), "RIGHT": set()}
            hunks.append(current)
            continue
        if current is None or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            current["RIGHT"].add(right)
            right += 1
        elif raw.startswith("-"):
            current["LEFT"].add(left)
            left += 1
        else:
            current["LEFT"].add(left)
            current["RIGHT"].add(right)
            left += 1
            right += 1
    return hunks


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_shape(draft: Any) -> List[str]:
    """Return every structural problem in the draft."""
    if not isinstance(draft, dict):
        return ["the draft must be a JSON object"]
    errors: List[str] = []
    if not isinstance(draft.get("repo"), str) or not REPO_RE.match(draft["repo"]):
        errors.append('"repo" must be "owner/name"')
    if not _positive_int(draft.get("pr")):
        errors.append('"pr" must be a positive integer')
    if not isinstance(draft.get("commit_id"), str) or not SHA_RE.match(draft["commit_id"]):
        errors.append('"commit_id" must be the full 40-character head SHA you reviewed')
    model = draft.get("model")
    if not isinstance(model, str) or model.strip().lower() in PLACEHOLDER_MODELS:
        errors.append('"model" must name the model writing the review, for example "Claude Opus 5.5"')
    summary = draft.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append('"summary" must be non-empty Markdown')
    elif "[!NOTE]" in summary:
        errors.append('"summary" must not include the disclosure; this script adds it')
    comments = draft.get("comments", [])
    if not isinstance(comments, list):
        errors.append('"comments" must be a list')
        return errors
    anchors: Counter = Counter()
    for index, comment in enumerate(comments, start=1):
        label = f"comment {index}"
        if not isinstance(comment, dict):
            errors.append(f"{label}: must be an object")
            continue
        unknown = sorted(set(comment) - COMMENT_KEYS)
        if unknown:
            errors.append(f"{label}: unknown keys {unknown}")
        path, line, start = comment.get("path"), comment.get("line"), comment.get("start_line")
        if not isinstance(path, str) or not path:
            errors.append(f'{label}: "path" is required')
        if not _positive_int(line):
            errors.append(f'{label}: "line" must be a positive integer')
        if start is not None and (not _positive_int(start) or (_positive_int(line) and start >= line)):
            errors.append(f'{label}: "start_line" must be a positive integer below "line"')
        for key in ("side", "start_side"):
            if key in comment and comment[key] not in SIDES:
                errors.append(f'{label}: "{key}" must be RIGHT or LEFT')
        if not isinstance(comment.get("body"), str) or not comment["body"].strip():
            errors.append(f'{label}: "body" must be non-empty Markdown')
        anchors[(path, line, comment.get("side", "RIGHT"))] += 1
    for (path, line, side), count in anchors.items():
        if count > 1:
            errors.append(f"{count} comments share {path}:{line} ({side}); merge them into one")
    return errors


def normalize_comment(comment: Dict[str, Any]) -> Dict[str, Any]:
    side = comment.get("side", "RIGHT")
    normalized = {"path": comment["path"], "line": comment["line"], "side": side, "body": comment["body"].strip()}
    if comment.get("start_line") is not None:
        normalized["start_line"] = comment["start_line"]
        normalized["start_side"] = comment.get("start_side", side)
    return normalized


def ordered_comments(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group comments by file in first-appearance order, then sort each file's comments by line."""
    file_order: Dict[str, int] = {}
    for comment in comments:
        file_order.setdefault(comment["path"], len(file_order))
    normalized = [normalize_comment(comment) for comment in comments]
    return sorted(normalized, key=lambda c: (file_order[c["path"]], c["line"], c.get("start_line", c["line"])))


def build_payload(draft: Draft, login: str) -> Payload:
    disclosure = DISCLOSURE.format(model=draft["model"].strip(), login=login)
    return {
        "commit_id": draft["commit_id"],
        "body": f"{disclosure}\n\n{draft['summary'].strip()}",
        "comments": ordered_comments(draft.get("comments", [])),
    }


def digest(payload: Payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _hunk_index(hunks: List[Dict[str, Set[int]]], side: str, line: int) -> Optional[int]:
    for index, hunk in enumerate(hunks):
        if line in hunk[side]:
            return index
    return None


def anchor_errors(comments: List[Dict[str, Any]], files: Dict[str, Optional[str]]) -> List[str]:
    """Check each normalized comment against the PR's per-file patches (path -> patch or None)."""
    errors: List[str] = []
    parsed: Dict[str, List[Dict[str, Set[int]]]] = {}
    for number, comment in enumerate(comments, start=1):
        path, line, side = comment["path"], comment["line"], comment["side"]
        where = f"comment {number} ({path}:{line})"
        if path not in files:
            errors.append(f"{where}: this file is not part of the PR's diff")
            continue
        patch = files[path]
        if not patch:
            errors.append(f"{where}: GitHub shows no diff for this file (binary or too large); move the point to the summary")
            continue
        hunks = parsed.setdefault(path, parse_patch(patch))
        end_hunk = _hunk_index(hunks, side, line)
        if end_hunk is None:
            errors.append(f"{where}: line {line} ({side}) is outside the diff hunks; anchor to a changed or context line")
            continue
        if "start_line" in comment and _hunk_index(hunks, comment["start_side"], comment["start_line"]) != end_hunk:
            errors.append(f"{where}: start_line {comment['start_line']} must be in the same diff hunk as line {line}")
    return errors


def _anchor_label(comment: Dict[str, Any]) -> str:
    if "start_line" in comment:
        label = f"Lines {comment['start_line']}-{comment['line']}"
    else:
        label = f"Line {comment['line']}"
    return f"{label} (removed code)" if comment["side"] == "LEFT" else label


def render_review(draft: Draft, payload: Payload) -> str:
    """Render the exact review that `post` would submit, numbered in posting order."""
    lines = [
        f"Review of {draft['repo']}#{draft['pr']} at {draft['commit_id'][:7]}",
        "",
        "## Review summary",
        "",
        payload["body"],
        "",
    ]
    current_path = None
    for number, comment in enumerate(payload["comments"], start=1):
        if comment["path"] != current_path:
            current_path = comment["path"]
            lines += [f"## `{current_path}`", ""]
        lines += [f"**{number}. {_anchor_label(comment)}**", "", comment["body"], ""]
    lines.append(f"Digest: {digest(payload)}")
    return "\n".join(lines)


def _anchor_key(comment: Dict[str, Any]) -> Tuple[Any, ...]:
    return (comment.get("path"), comment.get("line"), comment.get("side") or "RIGHT", comment.get("start_line"))


def verify_posted(payload: Payload, review: Dict[str, Any], posted: List[Dict[str, Any]]) -> List[str]:
    """Compare the posted review with the approved payload."""
    problems: List[str] = []
    posted_body = (review.get("body") or "").replace("\r\n", "\n").strip()
    if posted_body != payload["body"].strip():
        problems.append("the posted review body differs from the approved summary")
    expected = Counter(_anchor_key(c) for c in payload["comments"])
    actual = Counter(_anchor_key(c) for c in posted)
    for key in sorted(expected - actual, key=str):
        problems.append(f"missing comment at {key[0]}:{key[1]} ({key[2]})")
    for key in sorted(actual - expected, key=str):
        problems.append(f"unexpected comment at {key[0]}:{key[1]} ({key[2]})")
    return problems


# --------------------------------------------------------------------------- GitHub access


class GitHub:
    """Thin wrapper over `gh api`; tests replace it with a fake."""

    def __init__(self, runner: Callable[..., Any] = subprocess.run) -> None:
        self._runner = runner

    def _api(self, args: List[str], stdin: Optional[str] = None) -> str:
        try:
            proc = self._runner(["gh", "api", *args], input=stdin, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise DraftError("the GitHub CLI (gh) is not installed") from exc
        if proc.returncode != 0:
            endpoint = next((arg for arg in args if arg.startswith(("repos/", "user"))), " ".join(args))
            detail = (proc.stderr or proc.stdout or "").strip()
            raise DraftError(f"gh api {endpoint} failed: {detail}")
        return proc.stdout

    @staticmethod
    def _json_lines(text: str) -> List[Dict[str, Any]]:
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def login(self) -> str:
        return json.loads(self._api(["user"]))["login"]

    def pull(self, repo: str, pr: int) -> Dict[str, Any]:
        data = json.loads(self._api([f"repos/{repo}/pulls/{pr}"]))
        return {
            "head_sha": data["head"]["sha"],
            "state": data["state"],
            "merged": bool(data.get("merged")),
            "author": data["user"]["login"],
            "url": data["html_url"],
        }

    def files(self, repo: str, pr: int) -> Dict[str, Optional[str]]:
        out = self._api(["--paginate", f"repos/{repo}/pulls/{pr}/files?per_page=100", "--jq", ".[] | {filename, patch}"])
        return {item["filename"]: item.get("patch") for item in self._json_lines(out)}

    def create_review(self, repo: str, pr: int, payload: Payload) -> Dict[str, Any]:
        out = self._api(["--method", "POST", f"repos/{repo}/pulls/{pr}/reviews", "--input", "-"], stdin=json.dumps(payload))
        return json.loads(out)

    def review_comments(self, repo: str, pr: int, review_id: int) -> List[Dict[str, Any]]:
        jq = f".[] | select(.pull_request_review_id == {int(review_id)}) | {{path, line, start_line, side}}"
        out = self._api(["--paginate", f"repos/{repo}/pulls/{pr}/comments?per_page=100", "--jq", jq])
        return self._json_lines(out)


# --------------------------------------------------------------------------- workflows


def load_draft(path: str) -> Draft:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise DraftError(f"cannot read {path}: {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise DraftError(f"{path} is not valid JSON: {exc}") from exc


def live_check(draft: Draft, gh: GitHub) -> Tuple[Payload, str, Dict[str, Any], List[str]]:
    """Validate the draft against the live PR. Returns (payload, login, pull, warnings)."""
    errors = validate_shape(draft)
    if errors:
        raise DraftError("\n".join(errors))
    login = gh.login()
    pull = gh.pull(draft["repo"], draft["pr"])
    if pull["head_sha"] != draft["commit_id"]:
        raise DraftError(
            f"the PR head moved from {draft['commit_id'][:7]} to {pull['head_sha'][:7]}; "
            "review the new commits, update the findings and anchors, re-render, and get approval again"
        )
    payload = build_payload(draft, login)
    errors = anchor_errors(payload["comments"], gh.files(draft["repo"], draft["pr"]))
    if errors:
        raise DraftError("\n".join(errors))
    warnings = []
    if pull["state"] != "open":
        warnings.append(f"the PR is {'merged' if pull['merged'] else pull['state']}")
    return payload, login, pull, warnings


def post_review(draft: Draft, gh: GitHub, event: str, approved_digest: str, out: TextIO) -> int:
    if event not in EVENTS:
        raise DraftError(f"--event must be one of {', '.join(EVENTS)}")
    payload, login, pull, warnings = live_check(draft, gh)
    current = digest(payload)
    if current != approved_digest:
        raise DraftError(
            f"digest {approved_digest} does not match the current draft ({current}); "
            "re-render, show the user the full drafts, and get approval again"
        )
    if event != "COMMENT" and pull["author"].lower() == login.lower():
        raise DraftError(f"@{login} wrote this PR; GitHub only allows COMMENT reviews on your own pull request")
    for warning in warnings:
        print(f"warning: {warning}", file=out)
    review = gh.create_review(draft["repo"], draft["pr"], dict(payload, event=event))
    posted = gh.review_comments(draft["repo"], draft["pr"], review["id"])
    print(f"posted: {review.get('html_url')}", file=out)
    print(f"event: {event} (state {review.get('state')}), comments: {len(posted)} of {len(payload['comments'])}", file=out)
    problems = verify_posted(payload, review, posted)
    if problems:
        print("verification failed; do not repost, report this to the user:", file=out)
        for problem in problems:
            print(f"  - {problem}", file=out)
        return 1
    print("verified: body and every comment anchor match the approved draft", file=out)
    return 0


def main(argv: Optional[List[str]] = None, gh: Optional[GitHub] = None, out: TextIO = sys.stdout, err: TextIO = sys.stderr) -> int:
    parser = argparse.ArgumentParser(description="Check, render, and post a GitHub PR review drafted for a user.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "render", "post"):
        command = commands.add_parser(name)
        command.add_argument("draft", help="path to the draft JSON file")
        if name == "post":
            command.add_argument("--event", required=True, choices=EVENTS, help="the posting mode the user chose")
            command.add_argument("--digest", required=True, help="digest of the render the user approved")
    args = parser.parse_args(argv)
    gh = gh or GitHub()
    try:
        draft = load_draft(args.draft)
        if args.command == "post":
            return post_review(draft, gh, args.event, args.digest, out)
        payload, login, _pull, warnings = live_check(draft, gh)
        if args.command == "check":
            print(
                f"OK: {len(payload['comments'])} comments anchored to {draft['repo']}#{draft['pr']} "
                f"at {draft['commit_id'][:7]}; posting account @{login}",
                file=out,
            )
        else:
            print(render_review(draft, payload), file=out)
        for warning in warnings:
            print(f"warning: {warning}", file=out)
        return 0
    except DraftError as exc:
        print(f"error: {exc}", file=err)
        return 1


if __name__ == "__main__":
    sys.exit(main())

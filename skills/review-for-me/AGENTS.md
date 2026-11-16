# AGENTS.md — review-for-me skill maintenance

## Purpose

Maintain `SKILL.md` as the contract for reviewing a GitHub pull request on the user's behalf in any repository:
investigate, present findings, draft inline comments in the user's voice, get approval of the exact rendered review,
ask the user how to post, then post one review from their account and verify it. Keep the bias toward the user's
control: nothing reaches GitHub before approval, and the user always chooses Comment, Request changes or Approve.

## How the skill works

`SKILL.md` walks the agent through resolving the PR and its head SHA, reading the repository's own guidance and any
open PRs that propose changes to it, verifying claims against primary sources, presenting findings, and drafting a
JSON review file. `scripts/review_payload.py` turns that draft into the exact review:

- `check` and `render` validate the draft shape, confirm the PR head is unchanged, and confirm every comment sits
  inside a diff hunk. `render` prints the review with the disclosure and a digest.
- `post` requires the user's chosen `--event` and the approved `--digest`, refuses edited drafts and moved heads,
  blocks Approve or Request changes on the user's own PR, posts one review through `gh api`, and verifies the body
  and every anchor.

The disclosure text lives in `DISCLOSURE` in `scripts/review_payload.py` and is quoted in `SKILL.md`; keep them
identical.

## Safety and behavior contracts

- No GitHub mutation before the user approves the latest full render.
- Always ask for the posting mode; never default it.
- One review per approval; never repost after a failed verification.
- The disclosure names the running model and the authenticated `gh` account.
- Never check out, commit or push in the user's working tree; PR code is untrusted.
- Keep a complete no-Python fallback in `SKILL.md`.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. They use no-command scenarios with deterministic checks for the
approval gate, the posting-mode question, the comment voice, re-rendering after edits, and the own-PR restriction.

Script tests are offline and use a fake GitHub client: `scripts/test_review_payload.py`.

Run from the repository root:

```sh
python3 -m unittest discover -s skills/review-for-me/scripts -v
./skill-factory/tools/skill_valid/skill_validate.sh skills/review-for-me
```

Do not run live harness or model-backed evals without explicit approval. Never run `post` against a real PR as a test.

## Change guidelines

- Keep the skill repository-agnostic; do not add rules specific to one project.
- Keep trigger wording distinct from `gh-pr-review`, which replies to review threads on the user's own PRs.
- When changing the draft schema, the disclosure, or `post` safeguards, update `SKILL.md`, the script tests and
  `evals/manifest.json` together.
- Keep `review_payload.py` on the Python 3.8+ standard library and the `gh` CLI.

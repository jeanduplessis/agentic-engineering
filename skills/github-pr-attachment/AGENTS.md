# AGENTS.md — GitHub PR attachment skill maintenance

## Purpose

Maintain `SKILL.md` as the publication contract for attaching existing local review artifacts to existing GitHub pull requests. Keep artifact production outside this skill. Preserve its bias toward explicit visibility review, confirmation before upload, conservative PR mutation, concurrent-edit detection, and rendered-result verification.

## How the skill works

`SKILL.md` accepts artifact records plus an exact PR, validates local upload compatibility, captures the existing PR body and repository visibility, previews the mutation, asks for confirmation, uploads through GitHub's authenticated web flow, then places the generated snippet in the approved body section or comment. It verifies that unrelated PR content remains intact and that the attachment renders and opens.

## Safety and behavior contracts

- Require confirmation before file selection because GitHub uploads immediately.
- Never depend on undocumented upload APIs or guessed attachment URLs.
- Preserve the PR title and unrelated body content.
- Detect concurrent body edits before applying `gh pr edit --body-file`.
- Make public-repository attachment visibility explicit.
- Never request passwords or 2FA codes, extract cookies, or record GitHub login.
- Treat uploaded-but-unreferenced blobs as orphaned uploads and report them.
- Keep recording, editing, transcoding, and substantive artifact validation outside this skill.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. They use no-command publication scenarios and deterministic checks for confirmation, visibility, browser upload, exact snippet capture, body preservation, concurrent-edit handling, and final verification.

Run the focused validator from the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/github-pr-attachment
```

Run repository Python tests when changing framework-facing eval files:

```sh
PYTHONPATH=skill-factory python3 -m unittest discover -s skill-factory -v
```

Do not run live harness or model-backed evals without explicit approval.

## Change guidelines

- Keep commands compatible with the current agent-browser workflow; retain the instruction to load `agent-browser skills get core --full` before browser work.
- Recheck GitHub's official attachment documentation before changing supported formats, codec advice, visibility, or size-limit guidance.
- Coordinate with `pr-create` rather than absorbing broader PR creation, push, title, or description-rewrite behavior.
- Preserve compatibility with the artifact output contract in `../video-evidence/SKILL.md` without requiring video-specific fields.
- Update deterministic evals whenever confirmation, mutation, visibility, or verification behavior changes.

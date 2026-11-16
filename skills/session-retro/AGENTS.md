# AGENTS.md — session-retro skill maintenance

## Purpose

Maintain `SKILL.md` as a retrospective workflow that turns a completed coding session into at most five evidence-backed, durable instruction candidates for user approval, without editing files.

## How the skill works

The skill resolves its context from the current conversation, a transcript file, or pasted text; scans fixed categories; separates clear-evidence candidates from a watchlist and do-not-persist notes; recommends one placement per candidate; and waits for approved item numbers before drafting edits.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/session-retro`, `/skill:session-retro`, or `$session-retro`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` passes a pasted session summary with repeated tool failures, a terminology correction, and a skipped validation step, then checks for the `## Candidate updates` and `## Next action` sections, `Placement:` and `Draft instruction:` fields, and a category label. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:session-retro` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/session-retro
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Keep the no-edit-until-approved contract and the evidence and privacy rules.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.

---
name: skill-creator
description: >-
  Create, edit, validate, evaluate, optimize, and package skills shared by Pi and OpenCode. Use when users want to create a
  skill from scratch, improve an existing skill, add deterministic evals, run repo-local skill validation, compare skill
  behavior, optimize a skill description, or prepare harness discovery and package metadata.
---

# Skill Creator

Create and improve canonical skills shared by Pi and OpenCode. Preserve equivalent baseline behavior. Allow harness-specific metadata or acceleration only when other harnesses ignore it safely and source instructions provide a complete shared fallback.

## Core loop

### Build

1. Clarify purpose, triggers, outputs, required tools, and safety boundaries.
2. Draft or edit `skills/<skill-name>/SKILL.md` with shared Pi/OpenCode frontmatter and concise executable instructions.
3. Add or update `skills/<skill-name>/AGENTS.md` for non-trivial maintenance context.
4. Add deterministic eval coverage under `skills/<skill-name>/evals/` when behavior can be checked.

### Validate and expose

1. Run deterministic validation first.
2. Run live harness eval/validation only with explicit user approval.
3. Iterate until user acceptance criteria pass.
4. Expose same canonical skill source through native discovery or local symlinks; never generate harness-specific variants.

## Shared skill shape

Use a directory containing `SKILL.md`:

```text
skills/<skill-name>/
  SKILL.md
  AGENTS.md              # recommended for maintained repo skills
  evals/                 # recommended for behavior coverage
    manifest.json
    evals.json           # optional legacy case source supported by tools.skill_eval
    grader.py            # optional deterministic grader
  references/            # optional on-demand docs
  scripts/               # optional helper scripts
  assets/                # optional templates/assets
```

`SKILL.md` frontmatter:

```yaml
---
name: skill-name
description: Specific capability and when an agent should use it.
license: MIT
compatibility: Requires local CLI foo in PATH.
allowed-tools: Bash(foo:*) Read
disable-model-invocation: true
---
```

Required shared fields: `name`, `description`. Portable optional fields include `license`, `compatibility`, and `metadata`.
Pi-specific fields such as `allowed-tools` and `disable-model-invocation` are allowed only when OpenCode safely ignores them and skill behavior does not depend on them. Keep `allowed-tools` space-delimited unless Pi's validator contract changes.

## Create a new skill

Resolve only missing decisions that affect behavior: skill name, triggers, public workflow, output format, required CLIs/files/network access, and safety gates.

1. Create `skills/<skill-name>/SKILL.md`.
2. Keep instructions direct and scoped. Put trigger language in `description`; put execution steps in body.
3. Use references only when they reduce main-file length or isolate optional detail.
4. Add `AGENTS.md` with Purpose, How the skill works, Eval and validation, and Change guidelines.

## Add evals

Prefer repo-local `tools.skill_eval`.

Minimal manifest:

```json
{
  "schema_version": 1,
  "skill": {"name": "skill-name", "path": "../SKILL.md"},
  "suites": [
    {
      "name": "workflow",
      "type": "workflow",
      "mode": "forced",
      "fixture": {"type": "empty"},
      "cases": [
        {
          "id": "basic",
          "prompt": "Ask for the behavior this skill should improve.",
          "checks": [{"id": "non-empty", "type": "non_empty_response"}]
        }
      ]
    }
  ],
  "configurations": {
    "with_skill": {"harness": "pi", "force_skill": true},
    "without_skill": {"harness": "pi", "force_skill": false}
  }
}
```

Run deterministic/static plumbing checks from the repo root when useful:

```bash
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m tools.skill_eval skills/<skill-name>/evals/manifest.json workflow --results /tmp/<skill-name>-eval --require-real
```

Choose `harness: "pi"` or OpenCode-compatible `harness: "kilo"` for real eval execution; evaluator choice must not change expected skill behavior. `--require-real` with live execution disabled should skip honestly; do not present skipped/static results as behavior evidence.
Run live behavior evals only with explicit approval:

```bash
SKILL_EVAL_ALLOW_LIVE=1 \
python3 -m tools.skill_eval skills/<skill-name>/evals/manifest.json workflow \
  --results /tmp/<skill-name>-live-eval --require-real
```

## Validate a skill

Use deterministic validation before live gates:

```bash
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
python3 -m unittest tools.skill_valid.tests.test_skill_validate_wrapper -v
```

Validate one skill deterministically through the repo-local wrapper:

```bash
./tools/skill_valid/skill_validate.sh skills/<skill-name>
```

Run live gates only with explicit approval, selecting the intended supported harness:

```bash
./tools/skill_valid/skill_validate.sh skills/<skill-name> --allow-live --harness <pi|kilo>
```

`tools.skill_valid` checks shared skill compatibility, eval manifests, skill-local `AGENTS.md`, LLM optimization readiness, optional live qualitative review, and optional live evals.

## Optimize descriptions

Description quality affects whether either harness selects a skill. Optimize with deterministic evidence first:

1. Review failed trigger/eval cases from `tools.skill_eval` results.
2. Rewrite the `description` to name concrete user intents and task keywords.
3. Keep under 1024 characters.
4. Avoid overfitting to one eval prompt; generalize to intent categories.
5. Re-run deterministic tests and, with approval, live harness evals.

Legacy description-optimization scripts in this skill are disabled. Prefer repo-local eval outputs plus direct editing.

## Activate and package

Keep `skills/<skill-name>/SKILL.md` as canonical source. Pi and OpenCode discover `~/.agents/skills` directly in supported setups; otherwise expose that same source through local symlinks. Never generate or maintain copied harness variants.

This repo is also a local Pi package. Root `package.json` exposes Pi resources through harmless `pi.skills` and `pi.prompts` metadata:

```json
{
  "keywords": ["pi-package"],
  "pi": {
    "skills": ["skills"],
    "prompts": ["commands/*.md"]
  }
}
```

For another package, create `package.json` with Pi metadata:

```json
{
  "name": "my-pi-package",
  "keywords": ["pi-package"],
  "pi": {
    "skills": ["./skills"],
    "prompts": ["./prompts"],
    "extensions": ["./extensions"],
    "themes": ["./themes"]
  }
}
```

Install/test package discovery:

```bash
pi install /absolute/path/to/package
pi install ./relative/path/to/package
pi -e ./relative/path/to/package
pi list
pi update
pi remove /absolute/path/to/package
```

## Legacy assets in this skill

- `scripts/run_eval.py`, `scripts/improve_description.py`, and `scripts/run_loop.py` are disabled legacy wrappers. Do not use them for new work.
- `scripts/package_skill.py` creates legacy `.skill` archives; prefer Pi package metadata and `pi install`.
- `eval-viewer/` and `agents/` are retained as historical/reference material unless explicitly migrated.
- Preserve `LICENSE.txt` attribution.

## Reporting

When done, report:

- skill files changed;
- evals added/updated;
- deterministic validation run;
- live harness gates run or explicitly skipped;
- canonical source and activation/package paths;
- open follow-up work.

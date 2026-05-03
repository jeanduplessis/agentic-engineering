---
name: skill-creator
description: >-
  Create, edit, validate, evaluate, optimize, and package Pi skills. Use when users want to create a skill from scratch,
  improve an existing skill, add deterministic evals, run repo-local skill validation, compare skill behavior, optimize a
  skill description, or prepare a local Pi package.
---

# Skill Creator

Create and improve Pi skills in this repo. Treat every skill as downstream-owned and Pi-native.

## Core loop

1. Clarify the skill's purpose, trigger conditions, expected outputs, required tools, and safety boundaries.
2. Draft or edit `skills/<skill-name>/SKILL.md` with Pi-compatible frontmatter and concise executable instructions.
3. Add or update `skills/<skill-name>/AGENTS.md` for maintenance context when the skill is non-trivial.
4. Add deterministic eval coverage under `skills/<skill-name>/evals/` when behavior can be checked.
5. Run deterministic validation first.
6. Run live Pi eval/validation only with explicit user approval.
7. Iterate on the skill and evals until the user's acceptance criteria pass.
8. Expose the skill through this repo's Pi package manifest or another Pi package layout.

## Pi skill shape

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
description: Specific capability and when Pi should use it.
license: MIT
compatibility: Requires local CLI foo in PATH.
allowed-tools: Bash(foo:*) Read
disable-model-invocation: true
---
```

Required fields: `name`, `description`.
Common optional Pi-supported fields: `license`, `compatibility`, `metadata`, `allowed-tools`, `disable-model-invocation`.
Keep `allowed-tools` space-delimited unless the Pi validator contract changes.

## Create a new skill

1. Ask only for missing decisions that affect behavior:
   - skill name;
   - when it should trigger;
   - public workflow steps;
   - expected output format;
   - required CLIs/files/network access;
   - safety limits and approval gates.
2. Create `skills/<skill-name>/SKILL.md`.
3. Keep instructions direct and scoped. Put trigger language in `description`; put execution steps in the body.
4. Use references only when they reduce main-file length or isolate optional detail.
5. Add `AGENTS.md` with Purpose, How the skill works, Eval and validation, and Change guidelines.

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

`--require-real` with live Pi disabled should skip honestly; do not present skipped/static results as behavior evidence.
Run live behavior evals only with explicit approval:

```bash
SKILL_EVAL_ALLOW_LIVE_PI=1 \
python3 -m tools.skill_eval skills/<skill-name>/evals/manifest.json workflow \
  --results /tmp/<skill-name>-live-eval --require-real
```

## Validate a skill

Use deterministic validation before live gates:

```bash
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
python3 -m unittest tools.skill_valid.tests.test_skill_validate_wrapper -v
```

Validate one skill through the repo-local wrapper only when live Pi/model gates are approved:

```bash
./tools/skill_valid/skill_validate.sh skills/<skill-name>
```

The wrapper invokes:

```bash
python3 -m tools.skill_valid skills/<skill-name> --allow-live-pi
```

`tools.skill_valid` checks Pi compatibility, eval manifests, skill-local `AGENTS.md`, LLM optimization readiness, live qualitative review, and live evals.

## Optimize descriptions

Description quality affects whether Pi selects a skill. Optimize with deterministic evidence first:

1. Review failed trigger/eval cases from `tools.skill_eval` results.
2. Rewrite the `description` to name concrete user intents and task keywords.
3. Keep under 1024 characters.
4. Avoid overfitting to one eval prompt; generalize to intent categories.
5. Re-run deterministic tests and, with approval, live Pi evals.

Legacy description-optimization scripts in this skill that called external non-Pi CLIs are disabled. Prefer repo-local eval outputs plus direct editing.

## Package for Pi

This repo is itself a local Pi package. Root `package.json` exposes Pi resources through `pi.skills` and `pi.prompts` metadata:

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
- live Pi gates run or explicitly skipped;
- package/install path;
- open follow-up work.

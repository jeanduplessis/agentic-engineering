# AGENTS.md — skills directory context

This directory contains canonical agent skills for Pi. Each skill should be self-contained, easy for agents to discover, behaviorally complete without harness-specific acceleration, and optionally measurable via the repo-level `skill-factory/tools/skill_eval` framework.

## Skill structure

Skills should normally live in their own directories:

```text
skills/<skill-name>/
  SKILL.md
  evals/
    manifest.json        # optional but recommended
    evals.json           # optional legacy/simple case data
    grader.py            # optional skill-local deterministic grader
```

`SKILL.md` is required for installable skills and should include at least this frontmatter:

```yaml
---
name: skill-name
description: Clear trigger description for when this skill should be used.
---
```

Then provide concise, actionable instructions. Include references, scripts, examples, or templates only when they materially improve execution reliability.

## Skill eval framework

Use `tools.skill_eval` for behavioral skill evaluation. It runs skill-owned manifests, creates isolated sandboxes, captures trace bundles, grades deterministic checks, compares configurations, and writes reports.

Primary commands:

```bash
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
```

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/<skill-name>/evals/manifest.json workflow \
  --results /tmp/<skill-name>-eval \
  --require-real
```

Live harness execution is gated; run live evals only when explicitly requested or approved:

```bash
SKILL_EVAL_ALLOW_LIVE=1 \
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/<skill-name>/evals/manifest.json workflow \
  --results /tmp/<skill-name>-live-eval \
  --require-real
```

See `skill-factory/tools/skill_eval/README.md` and `skill-factory/tools/skill_eval/AGENTS.md` for the runner contract.

## Eval-ready skill requirements

To be runnable by `tools.skill_eval`, add `skills/<skill-name>/evals/manifest.json` with:

- `schema_version`
- `skill.name`
- `skill.path` pointing to `../SKILL.md`
- at least one executable suite, normally `workflow`
- named configurations, normally `with_skill` and `without_skill`

Minimal manifest:

```json
{
  "schema_version": 1,
  "skill": {
    "name": "skill-name",
    "path": "../SKILL.md"
  },
  "suites": [
    {
      "name": "workflow",
      "type": "workflow",
      "mode": "forced",
      "fixture": {"type": "empty"},
      "cases": [
        {
          "id": "basic",
          "prompt": "Ask for behavior this skill should improve.",
          "checks": [
            {"id": "non-empty", "type": "non_empty_response"}
          ]
        }
      ]
    }
  ],
  "configurations": {
    "with_skill": {
      "harness": "pi",
      "force_skill": true
    },
    "without_skill": {
      "harness": "pi",
      "force_skill": false
    }
  }
}
```

Relative manifest paths resolve from the manifest directory, including `skill.path`, `legacy_evals`, `custom_grader`, and copy fixtures.

## Suites

Current runner support:

- `workflow`: executable; tests behavior when the skill is intentionally available.
- `regression`: executable; known-fixed real failures that should stay passing.
- `trigger`: executable through Pi only, with `mode: "natural"`, boolean `should_trigger` cases, and a target-only read-only discovery profile. Suite-local configurations default to `discovery` and must omit `force_skill`.
- `capability`: representable; not executed by the current runner.

For workflow suites, compare:

- `with_skill`: Pi advertises the target `SKILL.md` for discovery; the legacy `force_skill` flag does not prove a body read.
- `without_skill`: Pi omits the target skill.

Pi (`harness: "pi"`) is the only supported live harness. Static and replay modes remain available for synthetic checks.

## Checks and graders

Prefer deterministic checks. Built-in types include:

- `required_content`
- `forbidden_content`
- `regex`
- `json_field_equals`
- `non_empty_response`

Use skill-local `evals/grader.py` only when generic checks cannot express the domain contract. A custom grader should expose:

```python
def grade(response, case=None, context=None):
    return [
        {
            "id": "skill.contract",
            "type": "custom_contract",
            "status": "passed",
            "passed": True,
            "evidence": "what was checked",
            "details": None,
        }
    ]
```

The `context` may include:

- `configuration`
- `sandbox_path`
- `run_dir`
- `artifact_manifest`
- `workspace_diff`

Use these to grade generated files/artifacts, not just response prose.

## Fixtures and artifacts

Supported fixture types:

- `empty`: fresh isolated sandbox.
- `copy`: copy a fixture directory into the sandbox before the run.

Example:

```json
"fixture": {"type": "copy", "path": "fixtures/project"}
```

Each run writes a trace bundle under the results directory, including:

- `raw_output.json`
- `events.jsonl`
- `response.md`
- `timing.json`
- `usage.json`
- `metadata.json`
- `artifact_manifest.json`
- `workspace_diff.txt`
- `grade.json`

Process failures are not graded as content failures. Timeouts and nonzero harness exits produce `status: "process_failed"`, `grade.status: "not_graded"`, and `passed: null`.

## Regression workflow

When a real, graded failure is confirmed, promote it before changing the skill:

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval promote-regressions \
  skills/<skill-name>/evals/manifest.json \
  --results /tmp/<skill-name>-live-eval \
  --output skills/<skill-name>/evals/manifest.json \
  --source-bead <bead-id>
```

Trigger failure promotion is rejected because workflow regressions would lose natural-selection semantics. Preserve the trace and add a trigger case instead.

Promote only failed, non-skipped, real runs that represent actual skill behavior problems. Do not promote synthetic smoke failures, skipped runs, process timeouts, or grader false positives as canonical regressions.

## Expectations for new or changed skills

When adding or substantially changing a skill:

1. Keep `SKILL.md` trigger description precise.
2. Add or update workflow eval cases for core behavior.
3. Add deterministic checks or a skill-local grader for important contracts.
4. Run unit tests for `skill-factory/tools/skill_eval` after changing framework-facing eval files.
5. Run no-live `--require-real` validation to ensure the manifest uses real configs and skips honestly without live harness execution.
6. Run live harness eval only with explicit approval.
7. Preserve Pi behavior; optional metadata or acceleration must have a complete fallback.
8. Treat static/replay results as synthetic plumbing checks, not skill-quality evidence.

# Skill eval observer maintenance

## Purpose

Observe Pi's actual discovery catalog and restrict model reads for `tools.skill_eval` natural trigger probes.
Canonical source is this directory. Never edit or install through `~/.pi/agent/extensions`.

## Contract

- Remain inert without `SKILL_EVAL_OBSERVER_CONFIG`; the eval runner supplies it and explicitly loads `index.ts`.
- Append `skill_eval_context` JSONL to the runner-supplied `context_path`, outside the model-readable fixture.
  Pi redirects extension stdout to stderr in JSON mode; never rely on stdout for this evidence or inject it
  as a model-facing message. Keep catalog schema versioned.
- Capture only catalog/profile metadata and a prompt hash. Never log full system instructions, credentials,
  auth headers, or provider payloads.
- Permit only built-in reads of the frozen target or fixture; canonicalize paths and reject symlink escapes.
  This does not sandbox trusted extensions or their network access.
- The Python runner owns trace validation, grading, frozen hashes, and the live gate. Coordinate changes with
  `skill-factory/tools/skill_eval/trigger.py`, its README/AGENTS.md, and protocol tests.

## Verification

Run `node --test harness/pi/extensions/skill-eval-observer/tests/observer.test.mjs` and
`PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_trigger -v` from the repo root.
Keep tests offline. Live model evals require separate approval and a fixed run budget.

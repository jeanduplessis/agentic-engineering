# Skill eval observer

Private instrumentation for the repo's Pi trigger eval runner. The runner loads `index.ts` explicitly with
`--extension`; do not enable it for normal interactive sessions. It has no hooks or side effects unless
`SKILL_EVAL_OBSERVER_CONFIG` names the runner-generated JSON file containing `skill_path`, `workspace`, and
`context_path` (a sidecar outside the model-readable fixture).

The observer appends one `skill_eval_context` JSONL record per `agent_start` to `context_path`, containing the rendered skills
catalog, active tools, read-tool source, observed model/provider/thinking, and a system-prompt hash. It does
not record the full system prompt, auth data, or provider payloads, and does not inject model-facing messages.
Pi redirects extension stdout to stderr in JSON mode, so catalog evidence must use this sidecar rather than
stdout or parsed stderr. The Python runner verifies the catalog and grades read events; this extension does not grade responses.

Only reads of the frozen target or files inside the fixture workspace are allowed. Paths are canonicalized
before access checks and pinned before execution; symlink escapes and other tools are blocked. This is a
model-tool boundary, not an OS sandbox: explicitly configured provider extensions remain trusted code with
normal process permissions. Use only reviewed local extensions in eval profiles.

The runner disables ambient resources and supplies empty system/append prompt overrides so Pi uses its
native prompt with the controlled catalog. This profile tests initial selection in a target-only, read-only
session, not arbitrary skill workflows or competition among installed skills.

## Offline tests

With Node 24 (native TypeScript stripping):

```sh
node --test harness/pi/extensions/skill-eval-observer/tests/observer.test.mjs
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_trigger -v
```

Tests use fake hooks and fake Pi processes. They do not call models or establish skill activation quality.

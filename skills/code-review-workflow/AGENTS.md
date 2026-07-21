# AGENTS.md — code-review-workflow skill maintenance

## Purpose

Maintain `SKILL.md` as the router for deterministic review of local repository changes. The skill should guide `/review` and `@review-*` workflows across staged, unstaged, untracked, deleted, and branch-diff changes without editing code or running application logic. React Code Quality is the only focus allowed to run the required `react-doctor` static analyzer.

## How the skill works

`SKILL.md` selects which reference files a caller should load. `references/scope.md` resolves changed files and emits the `Resolved Review Scope` contract. `references/reviewer-core.md` defines shared reviewer constraints. `references/output.md` defines the Evidence / Trace / Impact output shape. Focus references under `references/` define security, logic, types, data, resources, style, and React criteria.

## Eval and validation

`evals/manifest.json` declares the workflow smoke eval. It force-loads `SKILL.md` and asks an inline `@review-logic` scenario to produce the required review-summary and Evidence / Trace / Impact fields.

Run deterministic validation from the repository root without live harness/model gates:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/code-review-workflow
```

Run live harness/model validation only with explicit approval:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/code-review-workflow --allow-live --harness kilo
```

## Change guidelines

- Keep `SKILL.md` concise; move detailed review rules into `references/`.
- Preserve no-edit behavior: no edits, commits, pushes, builds, tests, servers, or application-code execution during focus review.
- Keep the analyzer exception narrow: only React Code Quality may run `npx -y react-doctor@latest . --verbose --diff`, and only when React is applicable.
- Update `evals/manifest.json` when the routing contract or required output shape changes.
- Keep command and reference mentions aligned with the skill name `code-review-workflow`.
- Preserve equivalent Pi/OpenCode execution: native sub-agents and harness-specific parallelism are optional; sequential current-session focus review is required fallback.

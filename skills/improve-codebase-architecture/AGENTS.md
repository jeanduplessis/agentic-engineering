# AGENTS.md — improve-codebase-architecture skill maintenance

## Purpose

Maintain `SKILL.md` as a concise workflow for finding architectural friction and proposing deepening opportunities in codebases. Keep recommendations grounded in project domain language from `CONTEXT.md`, decisions in `docs/adr/`, and architecture vocabulary in `LANGUAGE.md`.

## How the skill works

`SKILL.md` defines the high-level review loop: read domain docs, explore code friction, present numbered deepening candidates, then run a grilling conversation once the user selects a candidate. Links: `LANGUAGE.md` for required terms, `DEEPENING.md` for dependency/testing guidance, `INTERFACE-DESIGN.md` for the design-it-twice pattern, `CONTEXT-FORMAT.md` for domain language updates, and `ADR-FORMAT.md` for recording load-bearing decisions.

Preserve core behavior when editing: use Module, Interface, Implementation, Depth, Seam, Adapter, Leverage, and Locality exactly; prefer domain terms from `CONTEXT.md`; treat ADRs as decisions not to re-litigate; present candidates before proposing interfaces; update domain language or offer ADRs only when decisions crystallize.

## Eval and validation

`evals/manifest.json` defines the forced workflow evaluation: load `SKILL.md`, copy `evals/fixtures/shallow-order-app`, ask the agent to inspect the fixture repo and present deepening candidates without editing files, then use `evals/grader.py` to check the response contract.

Run the local validity gate from the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/improve-codebase-architecture
```

This wrapper is deterministic by default; pass `--allow-live` and select a supported harness only with explicit approval. For a deterministic optimization check, run:

```sh
PYTHONPATH=skill-factory python3 -m tools.llm_optimal_check skills/improve-codebase-architecture/SKILL.md
```

## Change guidelines

- Keep `SKILL.md` compact and directly executable; move detailed guidance to `LANGUAGE.md`, `DEEPENING.md`, `INTERFACE-DESIGN.md`, `CONTEXT-FORMAT.md`, or `ADR-FORMAT.md`.
- Keep all `SKILL.md` resource links inside `skills/improve-codebase-architecture/` so the skill packages portably.
- Update `evals/manifest.json`, `evals/grader.py`, or `evals/fixtures/shallow-order-app` when the workflow prompt, required vocabulary, candidate shape, or read-only contract changes.
- Keep eval checks deterministic and focused on visible behavior: domain-aware candidate framing, required architecture vocabulary, no premature interface proposal, and no workspace edits.
- Preserve repo-wide skill conventions in `skills/AGENTS.md` unless that shared contract changes.

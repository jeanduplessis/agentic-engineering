# AGENTS.md — tdd skill maintenance

## Purpose

Maintain `SKILL.md` as the runtime contract for test-driven development using thin red-green-refactor vertical slices and beads_rust (`br`) task tracking for durable work.

## How the skill works

`SKILL.md` tells agents to connect substantial TDD work to one beads task, claim it before implementation, update notes/comments at meaningful slice boundaries, create linked beads for discovered follow-up work, and close the bead with validation context when done. It also preserves the TDD discipline: one behavior test at a time, public-interface tests, minimal implementation, then refactor only when green.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`; cases live in `evals/evals.json`. The evals check that the skill uses current `br` command syntax, skips beads for tiny same-session changes, avoids silent setup, and preserves vertical-slice TDD behavior.

Run deterministic validation from the repository root:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/tdd
```

Run live harness validation only with explicit approval:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/tdd --allow-live --harness pi
```

## Change guidelines

- Keep beads task commands aligned with the installed `br --help` and `skills/beads/SKILL.md`.
- Do not add silent `br init`, repair, sync, push, or storage mutation steps.
- Preserve the boundary: session-local checklist for tiny same-session work; beads task for durable, blocked, branching, or handoff-prone work.
- Preserve vertical slicing: one failing behavior test, minimal implementation, repeat; do not turn RED into bulk test authoring.
- Update `evals/evals.json` when the public TDD/beads behavior or command syntax contract changes.

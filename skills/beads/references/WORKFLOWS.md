# Advanced runtime workflows: formulas, molecules, wisps, and gates

Use this file when the user asks for reusable workflows, multi-step templates, temporary operational plans, or async waits. Command names and flags vary across releases; run `bd <command> --help` before invoking.

## Formulas and molecules

Current CLI families to inspect:

```bash
bd formula --help
bd cook --help
bd mol --help
bd mol pour --help
```

Concepts:

- **Formula** — workflow definition/template source.
- **Cook/proto** — compiled template form.
- **Molecule** — instantiated persistent work graph with parent-child/dependency relationships.
- **Pour** — instantiate a persistent molecule from a proto/template.

Typical flow:

```bash
bd formula list --json
bd formula show <formula-name> --json
bd cook <formula-name> --dry-run
bd mol pour <proto-id> --var name=value --json
bd mol show <molecule-id> --json
```

Use molecules when the same workflow recurs and the resulting work graph should persist, such as feature implementation checklists or review pipelines.

## Wisps

Wisps are ephemeral molecules for operational workflows that do not need durable long-term history.

```bash
bd mol wisp --help
bd mol wisp <proto-id> --var name=value --json
bd mol wisp list --json
```

Use a wisp when:

- the workflow is exploratory or operational;
- the user does not want it preserved as normal durable issue history;
- the plan is useful now but not part of long-term project memory.

Promote or recreate useful follow-up as normal beads before ending the session.

## Gates

Gates represent external waits such as human approval, timers, PR merges, CI runs, or cross-project conditions. They prevent downstream work from appearing ready until the condition is resolved.

Discover supported syntax:

```bash
bd gate --help
bd gate create --help
bd gate list --json
```

Typical examples:

```bash
bd gate create --type=human --blocks bd-deploy --reason="Need release approval" --json
bd gate create --type=timer --blocks bd-deploy --timeout=30m --json
bd gate create --type=gh:pr --blocks bd-deploy --await-id=42 --json
bd gate resolve <gate-id> --json
```

Use gates for real blocking waits, not as labels.

## Choosing the right advanced tool

| Need | Use |
| --- | --- |
| Repeatable persistent workflow | Formula/cook + `bd mol pour` |
| Track an instantiated workflow graph | `bd mol` commands |
| Temporary operational workflow | `bd mol wisp` |
| Wait for external condition | `bd gate` |
| Assign work across agents | Claim/assign/comments/dependencies |

## Agent cautions

- Do not invent formula schemas from memory; inspect formulas and help first.
- Ask before adding shared workflow template files.
- Use persistent molecules only when the graph has future value.
- When a wisp produces durable follow-up, create normal beads with `discovered-from` or comments that explain the provenance.

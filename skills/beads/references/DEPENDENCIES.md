# Dependencies and ready work

## Blocking semantics

```bash
br dep add <dependent> <dependency>
```

`<dependent>` waits on `<dependency>`. The dependency blocks the dependent until closed.

```bash
# Auth work waits for API setup:
br dep add br-auth br-api --json
```

Use real blocking edges only when ordering matters. Do not use blocker edges just to express "related" or "belongs to epic".

## Common relationship patterns

Discovered follow-up:

```bash
br create "Found auth edge case" \
  -t bug -p 2 \
  --description "Discovered while working on br-auth; details..." \
  --deps discovered-from:br-auth --json
```

Parent/epic hierarchy:

```bash
br create "Auth System" -t epic -p 1 --json
br create "Design login UI" --parent br-auth -t task -p 1 --json
br create "Backend validation" --parent br-auth -t task -p 1 --json
```

Soft/non-blocking relation:

```bash
br dep add br-frontend br-api --type related --json
```

## Dependency types

| Type | Blocks `br ready`? | Use |
|---|---:|---|
| `blocks` / default | Yes | Real ordering constraints |
| `parent-child` | Yes for parent/epic closure semantics | Epic/source hierarchy |
| `discovered-from` | No by convention unless project config differs | Provenance for follow-up work |
| `related` | No | Loose association |

Installed versions may support extra relationship types. Check `br dep add --help`.

## Inspect blockers

```bash
br ready --json                         # Issues with no open blockers
br ready --priority 1 --json
br ready --type bug --json
br ready --parent <epic-id> --recursive --json
br blocked --json                       # Issues and their blockers
br dep tree <id> --json                 # Dependencies this issue waits on
br dep tree <id> --direction up --json  # Dependents / descendants
br dep list <id> --json                 # Dependencies
br dep list <id> --direction up --json  # Dependents
br dep cycles --json                    # Circular dependency detection
```

`br ready` is the default queue for agents. Prefer it over scanning all open issues manually.

## Modeling guidelines

Blocking setup:

```bash
br dep add br-implementation br-setup --json
```

- Use a blocker when implementation cannot safely start until setup completes.
- Conceptually related tasks: use `--type related` or a comment.
- PRD/epic membership: create with `--parent <epic-id>`.
- Human approval, CI, PR review, credentials, or external waits:
  - create an explicit blocking task, or defer the waiting task;
  - explain the condition in notes/comments.
- Avoid cycles. If `br dep cycles --json` reports one, ask before restructuring existing project data.

## Epic completion

```bash
br dep list <epic-id> --direction up --type parent-child --json
br ready --parent <epic-id> --recursive --json
br epic status --json
br epic close-eligible --dry-run --json
```

Close an epic only when all children are complete or `br epic close-eligible --dry-run --json` reports it eligible.

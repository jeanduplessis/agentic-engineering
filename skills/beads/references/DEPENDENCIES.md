# Dependencies and ready work

Dependencies order work. The key semantic is:

```bash
bd dep add <dependent> <dependency>
```

`<dependent>` cannot start until `<dependency>` closes.

## Common patterns

```bash
# Auth depends on API; API blocks auth
bd dep add bd-auth bd-api --json

# Create and link discovered work in one command
bd create "Found auth edge case" \
  -t bug -p 1 \
  --description "Discovered while working on bd-auth; details..." \
  --deps discovered-from:bd-auth --json

# Soft relationship, does not block ready queue
bd dep add bd-frontend bd-api --type related --json
bd dep relate bd-frontend bd-api --json
```

## Dependency types

Common types include:

| Type | Blocks `bd ready`? | Use |
| --- | --- | --- |
| `blocks` | Yes | Normal prerequisite ordering |
| `parent-child` | Usually hierarchical | Epic/task structure |
| `discovered-from` | No/annotation | Follow-up found while doing another issue |
| `related` / `relates-to` | No | Informational connection |

Installed versions may include extra graph links such as `tracks`, `supersedes`, `caused-by`, `validates`, or `until`. Check `bd dep add --help` and related command help for exact support.

## Finding what can run

```bash
bd ready --json                 # Issues with no open blockers
bd ready --priority 1 --json
bd ready --type bug --json
bd blocked --json               # Issues and their blockers
bd dep tree <id> --json         # Dependency tree
bd dep list <id> --json         # Dependencies/dependents
bd dep cycles --json            # Circular dependency detection
```

`bd ready` is the default queue for agents. Prefer it over scanning all open issues manually.

## Direction trap

If you want **setup before implementation**:

```bash
bd dep add bd-implementation bd-setup --json
```

Do not reverse it. The first argument is the blocked/dependent issue; the second argument is the blocker/prerequisite.

## Parent/child epics

Hierarchical issues can be created with `--parent`:

```bash
bd create "Auth System" -t epic -p 1 --json
bd create "Design login UI" --parent bd-auth -p 1 --json
bd create "Backend validation" --parent bd-auth -p 1 --json
bd dep tree bd-auth --json
```

Use parent/child structure for decomposition; use blocking dependencies only for actual order constraints.

## External waits

For waits on PRs, CI, timers, or human approval, use gates if supported by the installed version:

```bash
bd gate --help
bd gate create --help
bd gate create --type=human --blocks bd-deploy --reason="Need approval" --json
```

For gate patterns, use the workflows reference from the SKILL.md reference index.

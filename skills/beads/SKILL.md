---
name: beads
description: >
  Runtime guidance for using beads_rust (`br`) as persistent, dependency-aware task
  memory for coding agents. Use when work may span sessions or context
  compaction, needs blockers/dependencies, ready-work discovery, handoffs,
  multi-agent coordination, or the user asks to create/track/resume tasks.
  Prefer a session-local checklist for simple same-session work.
license: MIT
compatibility: Requires the br CLI in PATH and an existing beads database in the target project. Initialize or change setup only when the user asks.
allowed-tools: Bash(br:*) Read
---

# Beads — persistent task memory for coding agents

Beads Rust (`br`) tracks durable work as dependency-linked issues.
Use it for project memory that should survive conversation loss, handoffs, and parallel work.
Use the runtime's session-local checklist for short linear work that will finish now.

## Source of truth for syntax

Prefer the installed CLI for exact flags:

```bash
br <command> --help
```

`br` is non-invasive: normal issue commands mutate `.beads/` only.
It never commits, pushes, pulls, installs hooks, or runs git for you.
Mutating commands auto-flush JSONL by default.
Run `br sync --flush-only` only as an explicit final export check before committing `.beads/`, after disabled auto-flush, or during recovery.
Do not run bare `br sync`.

## When to use br

Use br when:

- Work may continue after this session, compaction, or handoff.
- Dependencies, blockers, a parent/epic graph, or a ready queue matter.
- You discover follow-up work while implementing something else.
- Multiple agents or branches may coordinate through the same project state.
- The user asks to create/track issues, find ready work, resume prior work, or preserve context.

Skip br for a tiny same-session checklist with no future value. If a simple task branches, create a bead and capture current state.

See [references/BOUNDARIES.md](references/BOUNDARIES.md) for the full decision guide.

## Runtime protocol

1. **Check that br is usable**
   ```bash
   br --version
   br info
   ```
   If `br` is missing or no database exists, report that and ask before installing, initializing, importing, repairing, or changing setup.

2. **Find and inspect work**
   ```bash
   br ready --json
   br list --status in_progress --json
   br show <id> --json
   ```

3. **Claim work before editing**
   ```bash
   br update <id> --claim --json
   ```

4. **Record durable notes at natural breakpoints**
   ```bash
   br update <id> --notes "CURRENT: ... NEXT: ... DECISIONS: ..." --json
   ```
   Use notes for compact current-state summaries.

5. **Add comments for narrative handoffs or long context**
   ```bash
   br comments add <id> --message "Handoff note or review context" --json
   ```

6. **Capture discovered work without derailing the current task**
   ```bash
   br create "Found bug in auth" \
     --description "Observed while working on <id>; repro/context..." \
     -t bug -p 1 --deps discovered-from:<id> --json
   ```

7. **Close completed work with a useful reason**
   ```bash
   br close <id> --reason "Implemented X in path/file; validated with command; follow-up tracked as <id>" --json
   ```

8. **Export only when needed**
   ```bash
   br sync --flush-only
   ```
   Run only when asked to export JSONL before committing `.beads/`.
   Stage/commit `.beads/` only when asked for a git commit/PR workflow.

## Command habits for agents

- Use `--json` for reads/writes when available.
- Include useful `--description`, `--notes`, comments, and close reasons.
- Avoid interactive/editor workflows; use `br update` flags and `br comments add`.
- Quote titles/descriptions.
- Long comments: `br comments add <id> --file handoff.md --json`.
- Long issue descriptions: `--description "$(cat /tmp/body.md)"`.
- Current `br create` does not support `--body-file` or `--stdin`.

Queue/graph habits:

- Run `br ready --json` before asking what to work on.
- Run `br blocked --json` or `br dep tree <id> --json` when blockers are unclear.
- Direct children: `br dep list <epic-id> --direction up --type parent-child --json`.
- Descendants: `br dep tree <epic-id> --direction up --json`.
- Do not create a second durable tracker; link related work in br.
- Mention low-level storage only for setup, recovery, or collaboration failures.

## Dependency semantics

`br dep add <dependent> <dependency>` means **dependent depends on dependency**; dependency blocks dependent until closed.

```bash
# API must finish before auth can start:
br dep add br-auth br-api --json

# Soft/non-blocking relation:
br dep add br-frontend br-api --type related --json
```

Use `--deps discovered-from:<id>` for work found during another task.
Use `--parent <epic-id>` for implementation tasks under a PRD/epic.
See [references/DEPENDENCIES.md](references/DEPENDENCIES.md).

## Multi-agent and advanced workflows

For coordination beyond a single agent, use the installed CLI help first, then the references:

- Claiming, assignment, handoffs, comments, and dependencies: [references/MULTI_AGENT.md](references/MULTI_AGENT.md)
- Epics, deferred work, saved queries, and reusable operational patterns: [references/WORKFLOWS.md](references/WORKFLOWS.md)
- Setup only when the user asks: [references/SETUP.md](references/SETUP.md)

## Recovery and troubleshooting

Start with diagnosis, not destructive fixes:

```bash
br info
br where
br status --json
br sync --status --json
br doctor --json
```

If a command fails, check installed syntax with `br <command> --help`. Ask before running repair, migration, deletion, initialization, import, or setup-changing commands. See [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md).

## Reference index

- [references/CLI_REFERENCE.md](references/CLI_REFERENCE.md) — essential runtime commands
- [references/BOUNDARIES.md](references/BOUNDARIES.md) — br vs session-local checklist decision rules
- [references/RESUMABILITY.md](references/RESUMABILITY.md) — writing notes for future agents
- [references/DEPENDENCIES.md](references/DEPENDENCIES.md) — blockers, ready work, graph commands
- [references/MULTI_AGENT.md](references/MULTI_AGENT.md) — claiming, assignment, handoffs, coordination
- [references/WORKFLOWS.md](references/WORKFLOWS.md) — epics, defer/undefer, queries, external waits
- [references/SETUP.md](references/SETUP.md) — initialization/setup only when requested
- [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) — recovery playbooks

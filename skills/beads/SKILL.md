---
name: beads
description: >
  Runtime guidance for using beads (bd) as persistent, dependency-aware task
  memory for coding agents. Use when work may span sessions or context
  compaction, needs blockers/dependencies, ready-work discovery, handoffs,
  multi-agent coordination, or the user asks to create/track/resume tasks.
  Prefer a session-local checklist for simple same-session work.
license: MIT
compatibility: Requires the bd CLI in PATH and an existing beads database in the target project. Initialize or change setup only when the user asks.
allowed-tools: Bash(bd:*) Read
---

# Beads — persistent task memory for coding agents

Beads (`bd`) tracks durable work as dependency-linked issues. Use it for project memory
that should survive conversation loss, handoffs, and parallel work. Use the runtime's
session-local checklist for short linear work that will finish now.

## Source of truth for syntax

Prefer the installed CLI for exact flags:

```bash
bd <command> --help
```

`bd prime` may provide project-local workflow context. Treat it as local guidance, not
universal skill behavior. If it conflicts with this skill or the user request, follow
the user request and current `bd --help`. Avoid backend/version-control plumbing unless
the user explicitly asks.

## When to use bd

Use bd when:

- Work may continue after this session, compaction, or handoff.
- Dependencies, blockers, gates, or a ready queue matter.
- You discover follow-up work while implementing something else.
- Multiple agents or branches may coordinate through the same project state.
- The user asks to create/track issues, find ready work, resume prior work, or preserve context.

Skip bd for a tiny same-session checklist with no future value. If a simple task branches, create a bead and capture current state.

See [references/BOUNDARIES.md](references/BOUNDARIES.md) for the full decision guide.

## Runtime protocol

1. **Check that bd is usable**
   ```bash
   bd --version
   bd info
   ```
   If `bd` is missing or no database exists, report that and ask before installing, initializing, or changing setup.

2. **Find and inspect work**
   ```bash
   bd ready --json
   bd list --status in_progress --json
   bd show <id> --json
   ```

3. **Claim work before editing**
   ```bash
   bd update <id> --claim --json
   ```

4. **Record durable notes at natural breakpoints**
   ```bash
   bd update <id> --notes "CURRENT: ... NEXT: ... DECISIONS: ..." --json
   ```
   Use notes for compact current-state summaries.

5. **Add comments for narrative handoffs or long context**
   ```bash
   bd comment <id> "Handoff note or review context" --json
   ```

6. **Capture discovered work without derailing the current task**
   ```bash
   bd create "Found bug in auth" \
     --description "Observed while working on <id>; repro/context..." \
     -t bug -p 1 --deps discovered-from:<id> --json
   ```

7. **Close completed work with a useful reason**
   ```bash
   bd close <id> --reason "Implemented X in path/file; validated with command; follow-up tracked as <id>" --json
   ```

No generic session-end backend step exists in this skill. Do not run or report
low-level storage/version-control commands unless needed for the user's request.

## Command habits for agents

- Use `--json` for reads/writes when available.
- Include useful `--description`, `--notes`, and close reasons; future agents need context.
- Avoid interactive commands such as `bd edit`; use `bd update` flags instead.
- Quote titles/descriptions; prefer comments or files for long text with backticks, quotes, or `$`.

- Run `bd ready --json` before asking what to work on.
- Run `bd blocked --json` or `bd dep tree <id> --json` when blockers are unclear.

- Do not create a second durable tracking system; link related work in bd instead.
- Do not mention low-level storage status unless the user asked about setup, recovery, or collaboration failures.

## Dependency semantics

`bd dep add <dependent> <dependency>` means **dependent depends on dependency**; dependency blocks dependent until closed.

```bash
# API must finish before auth can start:
bd dep add bd-auth bd-api --json

# Soft/non-blocking relation:
bd dep add bd-frontend bd-api --type related --json
# or, if installed version supports it:
bd dep relate bd-frontend bd-api --json
```

Use `--deps discovered-from:<id>` when creating work found during another task. See [references/DEPENDENCIES.md](references/DEPENDENCIES.md).

## Multi-agent and advanced workflows

For coordination beyond a single agent, use the installed CLI help first, then the references:

- Claiming, assigning, handoffs, comments, and dependencies: [references/MULTI_AGENT.md](references/MULTI_AGENT.md)
- Workflow templates, molecules, wisps, and gates: [references/WORKFLOWS.md](references/WORKFLOWS.md)
- Setup only when the user asks: [references/SETUP.md](references/SETUP.md)

## Recovery and troubleshooting

Start with diagnosis, not destructive fixes:

```bash
bd info
bd status --json
bd doctor --agent --json
```

If a command fails, check installed syntax with `bd <command> --help`. Ask before
running repair, migration, deletion, initialization, or setup-changing commands. See
[references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md).

## Reference index

- [references/CLI_REFERENCE.md](references/CLI_REFERENCE.md) — essential runtime commands
- [references/BOUNDARIES.md](references/BOUNDARIES.md) — bd vs session-local checklist decision rules
- [references/RESUMABILITY.md](references/RESUMABILITY.md) — writing notes for future agents
- [references/DEPENDENCIES.md](references/DEPENDENCIES.md) — blockers, ready work, graph commands
- [references/MULTI_AGENT.md](references/MULTI_AGENT.md) — claiming, assigning, handoffs, coordination
- [references/WORKFLOWS.md](references/WORKFLOWS.md) — templates, molecules, wisps, gates
- [references/SETUP.md](references/SETUP.md) — initialization/setup only when requested
- [references/TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) — recovery playbooks

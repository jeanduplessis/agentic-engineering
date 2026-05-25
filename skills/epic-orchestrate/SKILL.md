---
name: epic-orchestrate
description: "Use when asked to run, recover, or improve /epic-orchestrate; implement an existing ait epic; coordinate multi-issue child Pi gates; harden ait epic workflow; or resume a failed/interrupted epic orchestration. Orchestrates reconnaissance, per-issue implementation, validation, review, commits, final validation/review, closure, and recovery."
license: MIT
compatibility: Requires ait, git, and pi CLIs in PATH plus an existing .ait project in the target repo.
allowed-tools: Bash(ait:*) Bash(git:*) Bash(pi:*) Bash(mktemp:*) Read Write
---

# Epic Orchestrate

Implement one existing ait epic. The parent session is the controller; spawned Pi instances run formal gates.

When using `ait`, load and follow the `ait-cli` skill.

## Core invariants

Scope and ownership:

- Work only under the supplied epic. Do not create a replacement epic.
- Require a clean worktree before starting and before selecting each new issue.
- Parent owns queueing, gate interpretation, issue lifecycle updates, issue closure, commits, resume behavior, final validation/review, and epic closure.

Child permissions:

- Child gates must not stage, commit, close issues, force-close issues, or directly edit `.ait/` files.
- Implementation children may edit code/tests and propose or create needed follow-up ait issues only when the parent prompt explicitly permits it.
- Validation children are read-only.
- Review children may edit code/tests to fix findings, but must not stage, commit, comment on issues, update issues, or close issues.

Ait safety:

- Do not run bare `ait` in automation.
- Use the `ait` CLI as the only mutation surface; never edit `.ait/state.sqlite` or `.ait/issues.jsonl` directly.
- Mutating commands require `--actor agent` unless the user specifies another actor.
- Parse JSON envelopes for mutating commands.
- Continue only when `ok: true`; on `ok: false`, stop and report `error.code`, `error.message`, and next safe action.
- Do not force-close, initialize, import, delete, repair, or rewrite `.ait/` unless the user explicitly approves.

## Workflow

### Setup

Run:

```bash
ait --version
ait check
ait show <epic-id>
ait list --parent <epic-id>
ait ready --grouped
git status --short
git branch --show-current
git rev-parse --show-toplevel
```

Stop if `ait` is unavailable, no `.ait/` project exists, the epic ID is invalid, the target is not an epic/container/parent, or the worktree is dirty.

### Workdir and recon

- Create a temp workdir outside the repo for prompts, child outputs, diff snapshots, and append-only state files.
- Run the reconnaissance child gate.
- Build the issue queue from `ait list --parent <epic-id>` cross-checked against `ait ready --grouped`.
- Treat descendant scope as the epic's child issues unless current ait behavior explicitly supports nested descendants.
- If nested descendants exist, include only ready executable leaf issues under the epic.

### Per-issue loop

For each ready open descendant issue, run in order:

1. parent claim via `ait --actor agent claim <issue-id>`;
2. implementation gate;
3. validation gate;
4. pre-review diff snapshot;
5. review gate;
6. post-review diff snapshot;
7. validation again if review changed the diff;
8. parent marks satisfied acceptance criteria done via `ait --actor agent update <issue-id> --stdin` when needed;
9. parent issue closure via `ait --actor agent close <issue-id> --reason "<delivered and validated summary>"` after all required gates pass;
10. `ait check` after lifecycle mutations;
11. exact-path staging only, including code/test files and ait state files produced by CLI mutation/export when needed;
12. one issue commit;
13. clean-worktree check before continuing.

### Final epic pass

When all descendants are closed:

1. run final epic validation;
2. run final full code review;
3. rerun epic validation if final review changed the diff;
4. parent marks epic acceptance criteria done via `ait --actor agent update <epic-id> --stdin` when needed;
5. close the epic via `ait --actor agent close <epic-id> --reason "<delivered and validated summary>"`;
6. run `ait check`;
7. commit final ait/review changes if any.

### Final response

Report:

- epic ID/title;
- temp workdir;
- recon output;
- completed/skipped issues;
- child gate output paths;
- validation/review commands;
- commits;
- changed files;
- follow-up ait issues;
- blockers;
- final epic status;
- worktree status.

## Child prompt rules

Before every child invocation, write a self-contained prompt file.

Each child prompt must include:

- target ID;
- gate name;
- user instructions/focus notes;
- repo root and branch;
- relevant repo state;
- reconnaissance output path when available;
- gate-specific contract;
- warning not to rely on slash-command expansion;
- instruction not to stage, commit, close issues, update issues, add issue comments, force-close, or edit `.ait/` directly unless explicitly permitted.

Every child output must end with:

```text
GATE_STATUS: PASS|FAIL|BLOCKED
GATE_NAME: <recon|tdd-task|task-validate|code-review|epic-validate>
TARGET_ID: <ait issue id or epic id>
CHANGED_FILES: <comma-separated paths or none>
VALIDATION_COMMANDS: <commands/results or none>
BLOCKER: <none or concise blocker>
SUMMARY: <one concise summary>
```

Parent rules:

- Parse only the last `GATE_STATUS:` line.
- Continue only on `PASS`.
- Stop on non-zero `pi` exit, `FAIL`, `BLOCKED`, missing footer, ambiguous footer, mutating `ait` error envelope, or unsafe repo state.

## Template resolution

Before child prompt construction, discover templates for `/tdd-task`, `/task-validate`, `/code-review`, and `/epic-validate`.

Search:

- repo: `.pi/prompts/<name>.md`, `prompts/<name>.md`, `commands/<name>.md`, and root/nearest `package.json` `pi.prompts` entries;
- user: `~/.pi/agent/prompts/<name>.md`;
- installed Pi package prompt entries when discoverable.

Log the template used or exact searched paths. If unavailable, use this skill and references as the embedded fallback contract and state the fallback.

If a discovered template is beads/br-specific, use it only as behavioral inspiration.
The ait contract in `epic-orchestrate` wins: child prompts must use `ait` issue IDs and must not invoke `br`/beads unless the user explicitly asks.

## Script and state guidance

A helper orchestration script is generated operational scaffolding, not source of truth.

Before running any helper script:

```bash
bash -n <script>
```

Also preflight shell compatibility. Avoid `mapfile`/`readarray`, associative arrays, and Bash-version-specific expansions unless supported.

State files are append-only across resumes:

- use `touch` for missing state files;
- use `>>` for new entries;
- never truncate completed issues, commits, skipped closed issues, follow-up issues, or gate outputs.

## Recovery rule

Stop immediately on failed gates or unsafe state.

Report:

- gate name;
- target ID;
- output path;
- blocker;
- dirty files;
- next recommended action.

On resume, reuse prior state when available, inspect closed/open descendants and commits, and continue only after worktree and ait state are safe.

Reference details:

- `references/gate-contracts.md`
- `references/orchestration-protocol.md`
- `references/failure-recovery.md`

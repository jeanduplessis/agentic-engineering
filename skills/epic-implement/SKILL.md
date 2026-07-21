---
name: epic-implement
description: "Use when asked to run, recover, or improve /epic-implement; implement an existing beads epic; coordinate multi-task formal gates in Pi, OpenCode/Kilo, or another capable harness; harden epic workflow; or resume a failed/interrupted epic implementation. Orchestrates reconnaissance, per-task implementation, validation, review, commits, final validation/review, closure, and recovery."
license: MIT
compatibility: Requires br and git in PATH plus an existing beads database in the target repo. Native subagents or a harness runner are optional; sequential current-session execution is the required fallback.
allowed-tools: Bash(br:*) Bash(git:*) Bash(mktemp:*) Read Write
---

# Epic Implement

Implement one existing epic bead. The parent session is the controller; gate executors perform formal gates without taking parent-owned actions.

## Core invariants

Scope and ownership:

- Work only under the supplied epic. Do not create a replacement epic.
- Require a clean worktree before starting and before selecting each new task.
- Parent owns queueing, gate interpretation, task closure, commits, resume behavior, final validation/review, and epic closure.

Gate executor permissions:

- Gate executors must not stage, commit, or close beads.
- Implementation executors may edit code/tests and create needed follow-up beads.
- Validation executors are read-only.
- Review executors may edit code/tests to fix findings, but must not stage, commit, comment on beads, or close beads.

Sync:

- Never run bare `br sync`.
- Run `br sync --flush-only` only when explicitly requested by the user.

## Workflow

### Setup

Run:

```bash
br --version
br info
br show <epic-id> --json
br dep tree <epic-id> --direction up --json
git status --short
git branch --show-current
git rev-parse --show-toplevel
```

Stop if `br` is unavailable, no beads DB exists, the epic ID is invalid, the target is not an epic/container/parent, or the worktree is dirty.

### Workdir and recon

- Create a temp workdir outside the repo for prompts, gate outputs, diff snapshots, and append-only state files.
- Run the reconnaissance gate.
- Build the task queue from `br ready --parent <epic-id> --recursive --json`.

### Per-task loop

For each ready open descendant task, run in order:

1. implementation gate;
2. validation gate;
3. pre-review diff snapshot;
4. review gate;
5. post-review diff snapshot;
6. validation again if review changed the diff;
7. parent task closure after all required gates pass;
8. exact-path staging only;
9. one task commit;
10. clean-worktree check before continuing.

Do not parallelize gates that share a worktree or depend on earlier gate output.

### Final epic pass

When all descendants are closed:

1. run final epic validation;
2. run final full code review;
3. rerun epic validation if final review changed the diff;
4. close the epic;
5. commit final bead/review changes if any.

### Final response

Report:

- epic ID/title;
- temp workdir;
- recon output;
- completed/skipped tasks;
- gate output paths and execution methods;
- validation/review commands;
- commits;
- changed files;
- follow-up beads;
- blockers;
- final epic status;
- worktree status.

## Gate execution

For every gate, choose the first available method in this order:

1. native subagent support exposed by the current harness;
2. the current harness's non-interactive agent/runner capability;
3. sequential execution in the current session as a distinct gate role.

Pi self-invocation may be used as optional runner acceleration when available. It is never required.
Do not stop or weaken gates because Pi, native subagents, or an external runner is unavailable.

For current-session fallback, the controller must complete each gate before continuing:
Write the same self-contained prompt and adopt only that gate's permissions.
Perform the work, write its output/footer, return to the parent role, and interpret the result.
Preserve gate separation and parent-only closure/commit ownership.

Record the execution method and output path for every gate.
Treat a runner/subagent launch failure like any other failed execution.
If no runner works, use current-session fallback unless repository state is unsafe.

## Gate prompt rules

Before every gate execution, write a self-contained prompt file.

Each gate prompt must include:

- target ID;
- gate name;
- user instructions/focus notes;
- repo root and branch;
- relevant repo state;
- reconnaissance output path when available;
- gate-specific contract;
- warning not to rely on slash-command expansion;
- instruction not to stage, commit, or close beads unless explicitly permitted.

Every gate output must end with:

```text
GATE_STATUS: PASS|FAIL|BLOCKED
GATE_NAME: <recon|tdd-task|task-validate|code-review|epic-validate>
TARGET_ID: <bead id or epic id>
CHANGED_FILES: <comma-separated paths or none>
VALIDATION_COMMANDS: <commands/results or none>
BLOCKER: <none or concise blocker>
SUMMARY: <one concise summary>
```

Parent rules:

- Parse only the last `GATE_STATUS:` line.
- Continue only on `PASS`.
- Stop on non-zero executor exit, `FAIL`, `BLOCKED`, missing footer, ambiguous footer, or unsafe repo state.

## Template resolution

Before gate prompt construction, discover templates for `/tdd-task`, `/task-validate`, `/code-review`, and `/epic-validate` in this order:

1. this repository's Pi path `harness/pi/commands/<name>.md`;
2. current harness command/prompt locations and package entries when discoverable;
3. repo `prompts/<name>.md`;
4. optional Pi locations: `.pi/prompts/<name>.md`, root/nearest `package.json` `pi.prompts` entries, user `~/.pi/agent/prompts/<name>.md`, and installed Pi packages.

Log the template used or exact searched paths. If unavailable, use this skill and references as the embedded fallback contract and state the fallback. Template text informs the gate prompt; gate execution must not depend on slash-command expansion or any specific harness.

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
- never truncate completed tasks, commits, skipped closed tasks, follow-up beads, or gate outputs.

## Recovery rule

Stop immediately on failed gates or unsafe state.

Report:

- gate name;
- target ID;
- output path;
- execution method;
- blocker;
- dirty files;
- next recommended action.

On resume, reuse prior state when available, inspect closed/open descendants and commits, and continue only after worktree and bead state are safe.

Reference details:

- `references/gate-contracts.md`
- `references/orchestration-protocol.md`
- `references/failure-recovery.md`

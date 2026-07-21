# Failure Recovery

Stop immediately on failed gates or unsafe state.

Report:

- gate name;
- target ID;
- output path;
- blocker;
- dirty files;
- next recommended action.

## Resume rules

On resume:

- do not truncate prior orchestration state;
- reuse existing temp workdir if available;
- inspect completed commits;
- inspect closed/open descendant issue state;
- inspect dirty worktree;
- run `ait check`;
- continue from the failed target only after worktree and ait state are safe.

## Common failure modes

### Gate executor closed or mutated issue before validation failed

Corrective rule: implementation gate executors must not close, update, or comment on issues unless the parent prompt explicitly permits it. Parent closure happens after all gates pass.

If it already happened:

1. stop and report inconsistent state;
2. inspect `ait show <issue-id>` and gate outputs;
3. run corrective implementation gate with the validator blocker as context if work remains safe;
4. rerun validation/review;
5. commit only after state is safe and gates pass.

Do not force-reopen or force-close unless the user explicitly approves and ait supports the requested lifecycle action.

### Helper script failed mid-run

Do not continue blindly.

1. inspect worktree;
2. inspect gate outputs;
3. inspect `ait check` and relevant `ait show <id>` output;
4. patch or discard helper script;
5. preflight with `bash -n`;
6. resume from durable append-only state.

### Validation finds missed invariant path

Run a corrective implementation gate with the exact validator blocker as context.

Validation should include both:

- direct affected operation;
- later mutation that can invalidate existing related data.

### Ait mutation command returns `ok: false`

Stop and report:

- command;
- `error.code`;
- `error.message`;
- relevant `error.details`;
- next safe action.

Common next actions:

- `close_incomplete_acceptance_criteria`: mark proven criteria done or finish missing work.
- `close_open_children`: close/finish listed children first.
- `actor_required`: rerun the mutating command with `--actor agent`.
- `write_lock_busy`: wait, re-check state, and retry only if safe.

### Gate runner unavailable or failed

Try native subagent support, then the current harness runner. If neither works, complete the gate sequentially in the current session using the same prompt, contract, footer, and output path. Pi self-invocation is optional and its absence is not a blocker.

Stop instead of falling back only when repository or ait state is unsafe or the failed executor may have left ambiguous mutations.

### Prompt template unavailable or beads-specific

Use the embedded fallback contract.

Log:

- gate name;
- `harness/pi/commands/<name>.md` lookup;
- searched current-harness and repo prompt paths;
- optional Pi location/package discovery attempt;
- whether a discovered template was beads/br-specific;
- fallback contract used.

The ait contract wins over beads/br-specific template instructions.

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
- inspect closed/open descendant state;
- inspect dirty worktree;
- continue from the failed target only after state is safe.

## Common failure modes

### Child closed bead before validation failed

Corrective rule: implementation children must not close beads. Parent closure happens after all gates pass.

If it already happened:

1. report inconsistent state;
2. run corrective child implementation gate with the validator blocker as context;
3. rerun validation/review;
4. commit only after state is safe and gates pass.

### Helper script failed mid-run

Do not continue blindly.

1. inspect worktree;
2. inspect child gate outputs;
3. patch or discard helper script;
4. preflight with `bash -n`;
5. resume from durable append-only state.

### Validation finds missed invariant path

Run a corrective implementation child with the exact validator blocker as context.

Validation should include both:

- direct affected operation;
- later mutation that can invalidate existing related data.

### Prompt template unavailable

Use the embedded fallback contract.

Log:

- gate name;
- searched repo paths;
- searched user paths;
- installed-package discovery attempt;
- fallback contract used.

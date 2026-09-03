# Draft: pi-subagents 0.47.1 orchestration docs and workflow state reporting

**Status: local, unsubmitted issue draft.** No upstream issue has been opened. This audit inspected the installed `pi-subagents@0.47.1` package read-only; `package.json` confirms the version. All source paths and line ranges below refer to that installed release, not upstream HEAD. No live model runs or upstream regression tests were run.

## 1. Confirmed documentation defects and clarifications

### Replace the remaining public chain example

`skills/pi-subagents/references/prompting-and-roles.md:104–132` still teaches a three-stage `chain`, `{previous}`, `as`, and `{outputs.name}` handoff. This conflicts with the skill's `workflowScript`-only execution guidance. `src/extension/public-execution.ts:38–40` rejects top-level `chain` and parallel inputs before execution.

Replace that example and its surrounding handoff prose with `workflowScript`, `runs.run`, `runs.all`, and ordinary JavaScript result handling. Keep the single-writer boundary and parent approval of findings; do not turn unadjudicated reviewer output into automatic fix instructions.

### Explain oversized async completion previews

The execution reference recommends aggregating child outputs and consuming the aggregate before opening individual reports (`skills/pi-subagents/references/execution-controls.md:56–71`). That advice needs a size caveat:

- `src/runs/foreground/subagent-executor.ts:4660–4662` slices the formatted async return preview to 1,000 characters and separately caps the emitted-value preview at 1,000 characters. A long aggregate can therefore hide later findings from the completion summary.
- Lines 4664–4665 save the workflow value and per-child results separately from that summary. Preview truncation alone is not evidence that the underlying output was lost.
- `docs/observability.md:79–85` already explains that the one-shot result file is consumed, replay records expire, and output archives may be bounded. Saved output should not be described as an unlimited permanent ledger.

Add a short note beside the aggregation recipe: a completion preview is not the full report. Prefer a compact result index for large reviews, follow returned artifact references when fuller evidence is needed, and check that every assigned review lane is accounted for before claiming coverage. This does not require switching to foreground execution.

### Point readers to resolved output locations

`src/shared/artifacts.ts:160–195` selects project, session, or temporary artifact storage, with fallbacks when project/session information is missing. Debug filenames include the run ID, sanitized agent name, and optional index. Configured report outputs have their own resolution rules; `docs/observability.md:127–144` describes relative single-run outputs and the `singleRunOutputBaseDir` override.

These rules are already documented outside the parent recipes. Cross-link them from the large-output guidance and tell readers to use returned artifact paths or run metadata, rather than reconstructing a fixed path from an agent name or assuming `output: "review.md"` means the project root. Keep debug artifacts distinct from the configured report output.

## 2. Conditional stale terminal-step attention issue — not reproduced

Source inspection shows a mismatch worth testing:

- `src/runs/background/subagent-wait.ts:239–242`: `needsAttention` accepts either top-level `needs_attention` or that activity on **any** step, without checking the step's lifecycle status.
- `src/runs/foreground/subagent-executor.ts:4499–4509`: `projectWorkflowActivity` derives top-level attention only from running steps.
- The same executor at lines 4544–4566 updates a step to completed/failed without explicitly clearing its existing activity fields, then projects workflow activity.
- `src/runs/background/subagent-wait.ts:552–568`: attention ends a wait by default, including an all-runs wait. The surrounding active-run selection only considers queued/running roots.

**Conditional inference:** if a terminal step retains `needs_attention` while its workflow root and another step remain running, the wait predicate can report attention even when the top-level projection no longer does. This is not a claim that completed roots remain active, or that normal completion always leaves stale activity. Other progress updates may clear it before this combination is observed. The full transition has not been reproduced.

**Candidate remedy, pending reproduction:** align wait attention with live-step semantics while preserving historical step metadata and genuine attention from active children. A completion-triggered latch for every run would not address this specific mismatch.

## 3. Single-session observation: failed workflow, detached child

One local session was reported to show workflow failure and “resume-first” guidance while the actual child was still detached and awaiting a supervisor reply. This audit did not reproduce that observation; the private session trace is not included. It is separate from the conditional stale-step issue above, and neither establishes the other's cause.

Relevant source evidence:

- `src/runs/background/resume-guidance.ts:4–20` builds resume-first guidance from failed state and a persisted session file; that helper does not itself check whether the child remains detached.
- `src/runs/foreground/subagent-executor.ts:725–734` explicitly refuses revival while a remembered child is detached, directing the parent to reply and wait instead of launching a replacement.
- `src/runs/background/subagent-wait.ts:228–235` likewise gives reply-then-wait guidance for detached foreground children needing attention.

These paths confirm that the runtime distinguishes detached coordination from safe revival. They do not establish where the observed workflow/child disagreement arose. Investigate whether workflow reporting retains the live child's identity and pending supervisor state before choosing recovery guidance. Until clarified, inspect the actual child state and pending request rather than treating a failed workflow label as proof that the child has exited.

## Suggested deterministic checks — not run

1. **Documentation contract:** validate replacement launch examples against the public execution boundary without spawning a child. Cover supported `workflowScript` requests and rejection of legacy top-level chain inputs.
2. **Large-output retrieval:** use fixed child results with a finding beyond the preview limit. Verify that completion text is bounded and that returned references lead to the available full report. Cover configured artifact locations with temporary fixtures rather than fixed home-directory paths.
3. **Attention lifecycle:** feed a running workflow fixture with one terminal attention-marked step and one active non-attention step through the wait path. It should keep waiting until real completion or active attention; an active child awaiting a supervisor decision must still wake it. Drive transitions with a fake clock/events, not elapsed-time sleeps.
4. **Detached coordination:** use a local fake child and supervisor transport to request a decision, detach, receive a reply, and finish. Inspect workflow and child status during the pending reply, ensure guidance does not prescribe revival of a live detached child, and confirm the original child result is recovered without a replacement. Include a genuinely failed, non-detached child as the contrasting resume case.

The documentation corrections can proceed independently. Runtime changes need a focused reproduction first; this draft proposes neither changes to async defaults nor local patches to the installed package.

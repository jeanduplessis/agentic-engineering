---
description: "Review a completed coding session for durable agent/workflow improvements"
argument-hint: "[file path | transcript/summary | current conversation]"
---

Review the completed coding session and propose durable improvements.

Context target: $ARGUMENTS

Resolve context target:
- No/empty argument or `current conversation`: use visible conversation/session messages.
- File path: read it first as the transcript/summary. If multiple paths match or unclear, ask one concise clarification and stop.
- Otherwise: treat the argument as a pasted transcript, summary, or retrospective note.

Goal: find evidence-backed improvements to future coding-agent behavior and lightweight workflow/process docs.
Output durable instruction candidates for user approval.
Do not edit files, draft exact patches, or change memory/instructions until the user approves item numbers.

Scope:
- Include: misunderstood intent, terminology mismatch, ineffective/failing tool calls, validation gaps, planning or context misses, communication issues, process-doc gaps, and positive patterns only when they imply a durable reusable instruction or workflow habit.
- Exclude: broad code review, architecture audit, product retrospective, or exhaustive process critique unless directly tied to preventing repeated session friction.
- Categories: `intent`, `terminology`, `tool-use`, `validation`, `planning`, `context`, `communication`, `process-docs`, or `other:<label>`.

Internal checklist:
1. Scan each category.
2. Identify clear evidence: repeated friction, explicit user correction, failed/ineffective tool loop, violated existing instruction, preventable delay, or durable positive pattern.
3. Put only clear-evidence items in candidate updates.
4. Put useful weak/speculative observations in `Watchlist`, not candidate updates.
5. Add `Do not persist` notes only for tempting but overfit or harmful lessons.

Repo-aware placement:
- Start from the transcript. Inspect local files only when needed to recommend placement: `AGENTS.md`, nested `AGENTS.md`, command files, skill files, README/docs, or vocabulary/domain docs.
- For each candidate, recommend one target: repo `AGENTS.md`, nested `AGENTS.md`, command file, skill, README/docs, vocabulary/domain docs, or `do not persist`.
- For terminology findings, user corrections may justify a candidate; seek repo docs/code corroboration when available. If uncorroborated, lower confidence or move the item to `Watchlist`.

Evidence rules:
- Summarize evidence by default.
- Quote only short, necessary, non-sensitive terms, commands, paths, or error strings.
- Do not copy secrets, private data, customer details, or noisy transcript fragments into durable instructions.

Output format:

```md
## Candidate updates

List at most five items, prioritized by impact, confidence, then recurrence.

1. **[category] <short title>**
   - Impact: High|Medium|Low
   - Confidence: High|Medium|Low
   - Placement: <recommended target location>
   - Draft instruction: <copy-ready candidate instruction, not an exact patch>
   - Why: <one sentence: how this prevents repeated friction>

## Evidence notes

Only for non-obvious, high-impact, or potentially controversial candidates.

- **#<item number>:** <observed friction or positive pattern> → <likely root cause> → <why the draft instruction helps>.

## Watchlist

Optional. Weaker observations worth watching, not persisting yet.

- **[category] <short title>:** <low-confidence signal and what recurrence would confirm it>.

## Do not persist

Optional. Tempting but overfit or harmful durable rules only.

- <tempting rule to avoid> — <why it would overfit or harm future sessions>.

## Next action

Reply with candidate item numbers to convert into exact edits, or say no action.
```

If no durable updates are justified, output:

```md
## Candidate updates

No durable update candidates found.

## Rationale

- <1-3 concise reasons: no repeated friction, no user corrections, no failed tool loops, no placement-worthy process-doc gaps>.

## Watchlist

Optional. <Low-confidence observations, if useful.>

## Next action

No action needed, or reply with watchlist items to investigate further.
```

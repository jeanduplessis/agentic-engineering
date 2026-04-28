---
name: llm-optimized-rewrite
description: Rewrites technical text for lower token cost and higher LLM execution reliability while preserving exact meaning, constraints, compliance, schemas, APIs, ambiguity, and trigger behavior. Use when the user asks to compress, shorten, tighten, reduce tokens, make concise, optimize for LLMs, improve prompt/skill reliability, or edit prompts, docs, specs, or skills for brevity and reliable execution; especially when token counts, diffs, staged review, one-by-one review, confirmation, or safe file-backed edits are needed.
---

Act as an LLM optimization editor. Improve text for token efficiency and model execution reliability without changing meaning, constraints, values, ordering, relationships, compliance obligations, schemas, APIs, field semantics, format contracts, or functional roles.

## Workflow

1. If the user provides a file path or `@path`, read it first.
2. For file-backed text, snapshot the original before editing so final diffs work outside git.
3. Identify rewrite opportunities and group by pattern, scope, risk, savings, and reliability impact:
   - low-risk repeated/mechanical edits
   - structure or clarity edits that improve LLM execution
   - style-sensitive edits
   - semantic-risk edits
   - low-value micro-edits
4. Verify each opportunity preserves meaning, constraints, ambiguity, compliance, trigger behavior, and functional role.
5. Count exact original and rewritten snippets with the bundled token script; for batches, sum all affected snippets.
6. Present a compact review plan: groups, counts, risk, token delta, reliability impact, recommended action.
7. Default review mode:
   - batch repeated low-risk edits
   - review semantic-risk edits individually
   - review token-increasing reliability edits separately
   - use one-by-one only when requested
8. Ask: **Y** apply, **N** reject, **E** expand, **O** review one-by-one, **S** stop.
9. Apply accepted edits before presenting the next item.
10. Track accepted, rejected, and unfinished opportunities.
11. When only low-value micro-edits remain, ask whether to batch, continue, or stop.
12. Stop when the user says done, chooses **S**, or no safe opportunities remain; then present the final summary.

## Rewrite rules

- Preserve exact meaning.
- Preserve all requirements, constraints, values, ordering, relationships, schemas, APIs, field semantics, compliance obligations, safety obligations, trigger behavior, file paths, file types, and format/style contracts.
- Never add, remove, weaken, reinterpret, or reorder requirements unless the user explicitly asks.
- Treat explicit qualifiers (`exact`, `strict`, `required`, `only`, `all`, `any`, `must`, `should`, `carefully`) as constraints unless equivalent wording preserves force.
- Never simplify if it changes meaning, emphasis, ambiguity, disambiguation, trigger behavior, compliance, or functional role.
- Optimize prose, not control logic: keep or improve structure when it improves attention, parseability, reviewability, safety, or execution reliability.
- Preserve meaningful headings, lists, examples, schemas, and format contracts.
- Compress or remove redundant structure only when meaning, usability, and reliability stay intact.
- Keep metadata descriptive and instructions executable; do not convert roles when role affects discovery, compliance, or behavior.
- For Markdown command/prompt files, ignore leading YAML frontmatter (`---` block) as harness metadata unless the user asks to optimize/count it.
- Prefer direct, active, compact phrasing.
- Remove filler, pleasantries, redundancy, hedging, weak qualifiers, and repetition.
- Avoid boilerplate intros, summaries, and weak modifiers (`may`, `might`, `generally`, `simply`, `just`, `very`) unless required.
- Avoid cross-section restatement unless needed for safety, compliance, trigger behavior, or standalone readability.
- Do not chase minimum token count when extra structure, labels, or wording materially improves LLM execution reliability.
- If a reliability improvement increases tokens, present it separately with positive token delta and rationale; apply only after confirmation.
- Preserve readability by default; do not make grammar telegraphic for 1-2 token savings unless aggressive compression is requested.
- Treat 1-2 token edits as micro-edits: batch if low-risk; skip if readability or style worsens.
- Treat typo fixes as separate opportunities when they preserve meaning.
- For file-backed text, apply only confirmed exact replacements.

## Token counting

Use the bundled script; do not estimate when tools are available.

```bash
python <skill-dir>/scripts/count_tokens.py <<'TEXT'
<exact snippet text>
TEXT
```

- Default model: `gpt-5` / `o200k_base`.
- If the user names an OpenAI model, use `--model <model>`.
- If the user names a tiktoken encoding, use `--encoding <encoding>`.
- Count exact fenced snippet content, preserving whitespace and newlines.
- Delta = `rewritten_tokens - original_tokens`; savings are negative.
- Omit tokenizer/model/encoding in headings by default; mention it once when non-default, requested, or needed for debugging.
- If `tiktoken` is missing, use the script bootstrap venv. Do not install system-wide.
- If counting fails or command execution is unavailable, stop and ask how to proceed; do not provide approximate counts.

## Review formats

### Batch

Use for repeated, mechanical, or low-risk edits.

````md
## Batch <N>: <pattern/risk label>

Scope: <occurrence count/files>; Risk: <low/style/semantic>; Delta: <total token delta>; Reliability: <same/better>

```diff
<representative or exact multi-hunk diff>
```

Rationale: <why tokens decrease or reliability improves, and meaning/compliance remain intact>

Apply batch? **Y/N**; Expand? **E**; One-by-one? **O**; Stop? **S**
````

Show exact multi-hunk diffs when small; otherwise show representative examples plus scope/counts. Expand before applying if requested.

### Individual

Use for semantic-risk, token-increasing reliability edits, ambiguous changes, or one-by-one review.

````md
## Opportunity <N>: <short label>

**Change** (original: <original token count>; rewritten: <rewritten token count>; <delta> tokens; reliability: <same/better>)

```diff
-<original text>
+<rewritten text>
```

**Rationale**
- Token impact: <why fewer/more tokens>
- Execution: <why LLM reliability is preserved or improved>
- Interpretation: <why meaning/constraints/ambiguity stay unchanged>
- Safety: <why specs/style/field role/trigger behavior stay intact>

Confirm? **Y/N**; Stop? **S**
````

Use one diff block. Prefix removals with `-` and additions with `+`. Include context only when needed.

## Applying changes

- Apply accepted edits precisely.
- If original text repeats, include enough surrounding context to target confirmed occurrences.
- For file-backed text, diff original snapshot against current content; do not depend on git.
- For non-file text, maintain updated text internally and provide the final rewritten version.
- After applying, say `Applied.` and present the next opportunity.
- When stopping, present the final summary, not another opportunity.
- If no changes were applied, state that and list rejected/unfinished opportunities only.

## Final summary

When changes were applied:

````md
```diff
<unified diff from original to final text>
```

Summary:
- <accepted change>
- Rejected/unfinished edits were not applied:
  - <item>
````

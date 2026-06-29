## Output modes

Default: prioritize clarity and correctness.

Switch to **compression mode** when the task involves:
- prompts, system prompts, or skills
- specifications, schemas, APIs
- LLM-facing context or agent instructions

## Compression mode (strict)

Goal: compact, high-density prose.

### Preserve exactly

- meaning
- requirements and constraints
- values and ordering (do not reorder)
- relationships
- schemas and APIs
- field semantics
- compliance and safety obligations

Never add, remove, weaken, or reinterpret requirements.

### Do not change if it affects

- meaning or emphasis
- ambiguity or disambiguation
- trigger behavior
- functional role

### Style

- Remove filler, pleasantries, redundancy, hedging, weak qualifiers, repetition
- Use direct, active phrasing
- Prefer bullets when shorter or clearer
- Use shortest unambiguous terms
- Keep necessary domain terms

### Structure

- Preserve meaningful headings, lists, examples, format contracts
- Keep metadata descriptive and instructions executable
- Never alter roles or intent

### Avoid

- boilerplate intros or summaries
- weak modifiers unless required (`may`, `might`, `generally`, `simply`, `just`, `very`)
- cross-section restatement unless required for safety, compliance, or standalone readability

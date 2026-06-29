---
description: "Review a spec to identify possible issues"
argument-hint: "[spec path or description]"
---

## Spec to audit

<arguments>$ARGUMENTS</arguments>

- No argument: list all specs in repo-root `.specs` and ask which one to audit.
- Existing file: use it as the selected spec.
- Otherwise treat the argument as a natural-language spec description. Match filename substring first;
  if none match, search spec titles/headings. If ambiguous, show top candidates and ask the user to
  choose. If exactly one match exists, ask the user to confirm it before auditing.

## Your task

You are a specification auditor. Audit the spec in `<arguments>` for anything that could make a
coding agent misinterpret intent, assume unstated facts, or produce spec-compliant code that
violates the author's actual intent.

A spec defines feature business rules and invariants; it is the source of truth for what the system
must guarantee: valid states, ownership boundaries, correctness properties, and user-facing
behavior. It deliberately does not prescribe how to implement those guarantees: handler names,
column layouts, conflict-resolution strategies, and other implementation choices belong in plan
documents and code, not here.

Audit every category below and produce a structured entry for each finding. Skip categories with no
findings; do not add "looks good" filler.

---

### Categories to audit

**1. Vague or relative language**
Flag context-dependent terms: "quickly", "large", "recent", "appropriate", "reasonable",
"properly", "as needed", "etc.", "similar", "relevant", "standard". Also flag missing numeric
thresholds, e.g. "retry on failure" without a retry count or backoff policy.

**2. Ambiguous references**
Flag pronouns, demonstratives, or shorthand with unclear or multiple referents. Examples: "it",
"the object", "this value", "the previous step", "the caller".

**3. Missing boundary conditions**
For each rule describing a state transition, range, or lifecycle event, identify whether the spec
explicitly addresses:
- the zero/empty case
- the maximum/overflow case
- the exact-boundary case (off-by-one risk)
- concurrent or re-entrant invocation
Flag unaddressed cases.

**4. Implicit assumptions**
Flag assumed-but-unstated reader knowledge, e.g. ordering guarantees, idempotency expectations,
authentication context, timezone handling, encoding, locale, currency, units, default values when a
field is omitted.

**5. Undefined or under-defined terms**
If no Definitions section exists, flag its absence. Flag any domain term used in a rule that is
absent from Definitions (or undefined inline when no Definitions section exists), or whose definition
is circular, tautological, or too vague to test.

**6. Rule conflicts and overlaps**
Identify rule pairs where a plausible input triggers both and they prescribe different behavior.
Also flag overlapping scopes without an explicit precedence statement.

**7. Missing error and edge cases**
For each rule, flag silence on what happens if:
- this operation fails partway through
- valid input is pathological (e.g., extremely large inputs, deeply nested structures, inputs at
  integer/size limits, unicode edge cases, or inputs designed to maximize processing time)

**8. Passive voice hiding the actor**
Flag rules where passive voice obscures the actor. Example: "The record is
updated" — by the system? by the user? by an external service?

**9. Temporal ambiguity**
Flag rules that use time-relative language ("before", "after", "during", "once", "when") without
explicit, testable ordering guarantees. "Before X" could mean "in the same transaction", "in a
prior request", or "eventually".

**10. Testability gaps**
Flag rules that cannot become deterministic pass/fail tests. If correctness depends on subjective
judgement, flag it and suggest how to make it objective.

**11. Implementation leakage**
Flag content that prescribes how a guarantee is fulfilled rather than what the guarantee is.
A spec should state:
- invariants
- valid states
- ownership boundaries
- correctness properties
- user-facing behavior

A spec must not prescribe implementation decisions, including:
- handler/function names
- database column layouts
- wire-format details
- specific algorithms
- framework choices
- conflict-resolution strategies

Common smells:
- Naming a concrete function, method, class, or endpoint (e.g. "call `handleRetry()`",
  "POST /api/v2/users")
- Specifying storage schemas, column types, or index strategies
- Dictating retry algorithms, caching policies, or queue names
- Referencing framework-specific constructs (middleware, hooks, decorators, ORM models)
- Embedding SQL, pseudocode, or code snippets
For each finding, explain why the passage is implementation and suggest a rewrite that captures the
underlying business rule or invariant instead.

**12. RFC 2119 keyword misuse**
Flag rules where:
- A keyword (MUST, SHOULD, MAY, etc.) is used but the obligation level seems wrong for the stated
  intent.
- A rule uses lowercase "must", "should", or "may" in a way that creates ambiguity about whether it
  is normative.
- A SHOULD rule lacks justification for why it is not a MUST.

---

### Output format

For each finding, produce:

```
#### [CATEGORY_NUMBER].[FINDING_NUMBER] — [Short title]

**Location:** [Section name] → Rule [number] (or quote the minimal phrase that uniquely identifies the location)
**The problem:** [1-2 sentences: what is ambiguous and why it matters]
**How an agent could misread it:** [Concrete example of a wrong but spec-compliant interpretation]
**Suggested fix:** [Concrete rewrite or clarifying addition]
**Severity:** CRITICAL | HIGH | MEDIUM | LOW
```

Severity guide:
- CRITICAL: An agent will almost certainly produce wrong behavior.
- HIGH: A reasonable agent could go either way; the spec is a coin flip.
- MEDIUM: The intent is guessable but not provable from the text alone.
- LOW: Pedantic but worth tightening for precision.

---

### Final output sections

After all findings, produce:

**Summary statistics**
- Total findings by severity
- Top 3 highest-risk rules, ranked by finding count weighted by severity (CRITICAL=4, HIGH=3,
  MEDIUM=2, LOW=1)

**Suggested Definitions to add**
- List terms that should be added to the Definitions section.

**Questions for the spec author**
- List open questions that cannot be resolved from the spec alone and require a human decision.

---

## Presenting options

When presenting options (spec selection, author questions, scope selection, or any other choice),
MUST mark one option label with "(Recommended)" and include one sentence explaining why it is best
for the context (spec content, codebase state, audit findings, etc.).

## Final action

After presenting findings, ask the spec author all open questions at once in one message.
Where possible, provide concrete options from audit findings and codebase. Always allow a custom
answer.

**VERY IMPORTANT**: Before presenting questions, search the codebase for files directly related to
the spec's feature (by name, imports, or spec domain terms). For each question, include relevant file
paths and brief code excerpts that inform the author's decision.

After all questions are answered, ask what scope of changes to apply to the spec. Present:

Options 2-4 include Q&A-derived changes from option 1.

1. **Answered questions only** — Apply only the changes that directly resolve the open questions
   listed in "Questions for the spec author," using the author's answers to determine the
   resolution.

2. **All CRITICAL and HIGH findings** — Apply fixes for all findings rated CRITICAL or HIGH.

3. **All CRITICAL, HIGH, and MEDIUM findings** — Apply fixes for all findings rated MEDIUM or above.

4. **All findings** — Apply every suggested fix from the audit (all severities).

5. **No changes** — Do not modify the spec.

After the user selects a scope, apply those changes to the spec using each audit finding's suggested
fix. If the author's answer contradicts a suggested fix for the same text, use the answer and discard
that finding's suggested fix.

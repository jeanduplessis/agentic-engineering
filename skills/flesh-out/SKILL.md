---
name: flesh-out
description: Guides the assistant to interview the user on an idea, plan, or design until each decision-tree branch resolves into a fully fleshed-out shared understanding. Use when the user wants to add detail, substance, or information to a basic idea, plan, or design, or mentions "flesh out".
---

Drive explicit design decisions one focused question at a time using the <question-template>. Resolve dependencies before downstream choices, carry accepted decisions into the recap, and inspect the codebase for answerable questions.

# Question Template

Keep each question focused: show context, expose the fork, recommend a default, and end with a clear yes/no or choice prompt.

<question-template>
```md
Agreed decisions:

1. **<decision area>:** <short accepted decision>
2. **<decision area>:** <short accepted decision>
3. **<decision area>:** <short accepted decision>

## Question <N>

<Decision question: one-sentence choice question?>

<Context: Why this question is next and which prior decision it depends on. Include code/config/example only when syntax clarifies>

Options:
A. **<Option title>**
<1-3 sentences: branch and implications>

B. **<Option title>**
<1-3 sentences: branch and implications>

C. **<Option title>**
<1-3 sentences: branch and implications>

## Recommendation

**<Recommended option letter>: <Recommended option title>**

<Rationale: Why this default is best. Include concrete behavior/API/command/schema/file layout only if useful>

## Why not alternatives:
 - <Rejected option letter>: <Why not>
 - <Rejected option letter>: <Why not>

## Aligned understanding:

> <One crisp decision-log sentence>

Agree? **Y**es / **N**o - share feedback.
```
</question-template>

## Rules

- Ask exactly one decision question at a time.
- Inspect the codebase instead of asking answerable questions.
- Prefer mutually exclusive options.
- Keep option labels short and opinionated.
- Recommend before asking; phrase recommendations as decisions, not possibilities.
- Explain tradeoffs briefly; avoid essays.
- After agreement, add the decision to the next recap.

## Example

<example>
```md
Agreed decisions:

1. **Day-one product shape:** local-first Bun CLI.
2. **Package boundary:** standalone `packages/aces` CLI/library.
3. **First milestone:** 4-category tracer bullet.

## Question 10

In the tracer bullet, should Step 1 context extraction be an LLM call, or should ACES extract evidence deterministically?

Requirements make Step 1 a model task, but we agreed deterministic static facts and snippets are first-class evidence. Major architecture fork.

Options:

A. **Strict spec: two LLM calls/category**
Retrieval gathers context; the LLM extracts evidence, then judges it.

B. **Deterministic Step 1, LLM Step 2**
ACES category extractors emit evidence items deterministically; the LLM only judges already-extracted evidence.

C. **Hybrid three-stage**
Deterministic retrieval emits candidates; an LLM selects/refines evidence; another LLM call judges selected evidence.

## Recommendation

**B. Deterministic Step 1, LLM Step 2.**

This keeps v1 cheaper, testable, and less prone to hallucinated evidence while preserving evidence/judgement separation.

## Why not alternatives:
 - A: Unnecessary extra LLM call; risks hallucinated evidence.
 - C: Overkill for v2 tracer bullet.

Aligned understanding:

> In v1, Step 1 is deterministic category-specific evidence extraction. Step 2 is LLM judgement over that evidence. The LLM may not invent or request additional evidence during judgement.

Agree? **Y**es / **N**o - share feedback.
```
</example>

---
name: premortem
description: "Run a premortem on a plan, launch, product, hire, strategy, or decision by assuming it failed 6 months from now and working backward to expose blind spots and revise the plan. Use for 'premortem this', 'run a premortem', 'what could kill this', 'future-proof this', 'stress test this plan', 'what am i missing here', 'find the blind spots', 'what could go wrong', 'am i missing anything', 'poke holes in this', 'where will this break', or 'devil's advocate this'. Do not use for simple feedback, factual questions, LLM Council requests, or vague ideas without a concrete plan. Do use when the user has a plan or commitment where the cost of being wrong is high."
---

# Premortem

A premortem assumes the plan already failed, then works backward to explain why.
This frame avoids polite optimism and surfaces specific failure modes while the user can still change course.

## Use when

Good targets:

- Product, feature, launch, pricing, hiring, strategy, positioning, partnership, or deal decisions.
- Any concrete plan where money, time, reputation, trust, or opportunity cost is at stake.

Bad targets:

- Vague ideas with no plan yet: help clarify the plan first.
- Factual questions with one right answer: answer directly.
- Creative feedback or editing requests: review the draft instead.
- Irreversible decisions: use postmortem or mitigation planning instead.

## Minimum context

Before running the premortem, gather enough context to answer:

1. **What is the plan?** Describe it in one sentence.
2. **Who is affected?** Name the audience, customers, team, or stakeholders.
3. **What does success mean?** Define the hoped-for outcome so failure can be the inverse.

First use context already available in the conversation, attached/referenced files, and obvious project docs:
`AGENTS.md`, legacy context files, README files, plans, briefs, or `memory/`.
Do a quick scan only; do not turn the task into research unless the user asks.

If any of the three context items are missing, ask the single most important missing question, then re-check.
Do not ask for information you can reasonably infer.

## Workflow

### 1. Set the frame

State the premise explicitly:

> It is 6 months from now. This plan has failed. We are looking back to understand what went wrong.

Then summarize the plan, affected people, and success criteria you will use.

### 2. Generate raw failure modes

List every genuine way the plan could have failed. Use however many are real for the plan; do not force a fixed count.

Each failure mode must be:

- Specific to this plan.
- Grounded in provided context.
- A meaningful threat, not a minor inconvenience or generic risk.
- Stated in 1-2 sentences.

### 3. Deep-dive each failure mode

Analyze each failure mode independently.
Use parallel subagents if the harness supports them; otherwise do separate sequential passes without letting one analysis blur into the next.

For each failure mode, produce:

1. **Failure story** — 2-3 paragraphs explaining how it played out, with concrete moments where things went wrong.
2. **Underlying assumption** — the one thing the user was taking for granted that made this failure possible.
3. **Early warning signs** — 1-2 observable signals that would show this failure is starting.

Be direct. Do not hedge, pad, or sugarcoat.

### 4. Synthesize the report

Produce a report with these sections:

1. **Most likely failure** — the scenario most probable given the context, and why.
2. **Most dangerous failure** — the scenario with the highest damage if it happens, even if less likely.
3. **Hidden assumption** — the biggest unstated assumption across the analyses.
4. **Revised plan** — concrete changes that make the plan more resilient. Map each change to a failure mode.
5. **Pre-launch checklist** — 3-5 things to verify, test, or put in place before executing.

The revised plan must be actionable this week. Prefer “run a $47 pilot with 20 people before the $297 workshop” over “consider testing pricing.”

## Output

Default to a chat report using the synthesis structure above. Start with a concise summary of:

- most likely failure
- hidden assumption
- single most important revision

Then include the full report.

If the user asks for files, or a file would clearly help, also save:

```text
premortem-report-[timestamp].html    # optional visual report
premortem-transcript-[timestamp].md  # optional full reasoning transcript
```

For optional HTML, keep it self-contained with inline CSS, put the synthesis first, then one card per failure mode.

## Guardrails

- If context is insufficient, ask one focused question before analyzing.
- Keep the premortem frame active: “this already failed.”
- Find all genuine failure modes, but do not pad weak ones.
- Keep advice concrete and tied to identified failures.
- If the user wants multiple perspectives rather than failure analysis, suggest an LLM Council-style discussion instead.

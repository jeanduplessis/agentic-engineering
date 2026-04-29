---
name: flesh-out
description: Guides the assistant to interview the user on an idea/plan/design until each decision-tree branch resolves into a fully fleshed-out shared understanding. Use when the user wants to add detail, substance, or information to a basic idea/plan/design, or mentions "flesh out".
---

Use this workflow to turn a vague idea into explicit, agreed decisions. Ask one decision question at a time with the template below.

# Question format

Each question should show current agreement, expose the next fork, recommend a default, and end with a clear yes/no or choice prompt.

<question-template>
```md
Agreed decisions:

- **Accepted decision:** <short summary>
- **Another agreed choice:** <short summary>
- **Remaining settled context:** <short summary>

## Question <N>

<One-sentence decision question?>

<Why this choice is next. Include prior-decision dependencies, code, config, or examples only when they clarify the fork.>

Options:

A. **<Option title>**
<1-3 sentences: branch and implications.>

B. **<Option title>**
<1-3 sentences: branch and implications.>

C. **<Option title>**
<1-3 sentences: branch and implications.>

## Recommendation

**<Recommended option letter>: <Recommended option title>.**

<Rationale for the default. Add concrete behavior, API, command, schema, or file layout only if useful.>

## Why not alternatives

- <Rejected option letter>: <Why not.>
- <Other rejected option>: <Why not.>

## Aligned understanding

> <One crisp decision-log sentence.>

Agree? **Y**es / **N**o - share feedback.
```
</question-template>

## Rules

- Ask exactly one focused decision question at a time.
- Resolve dependencies before downstream choices.
- Inspect the codebase instead of asking answerable questions.
- Prefer mutually exclusive options with short, opinionated labels.
- Recommend before asking; phrase recommendations as decisions, not possibilities.
- Explain tradeoffs briefly; avoid essays.
- After agreement, add the decision to the next recap.

## Example pattern

For a CLI planning conversation, do not ask about packaging, tests, commands, and persistence at once.
Ask for the next highest-leverage fork, such as product shape or data model.
Then recommend the simplest default and log the aligned decision after the user agrees.

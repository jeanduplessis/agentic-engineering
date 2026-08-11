---
name: flesh-out
description: Guides the assistant to interview the user on an idea, plan, or design until each decision-tree branch resolves into shared understanding. Use when the user wants to add detail, substance, or information to a basic idea, plan, or design, or mentions "flesh out".
---

Use this workflow to turn a vague idea into explicit, accepted decisions. Ask one focused decision question at a time.

# Question format

Do not routinely recap settled decisions before each question.
Keep a running decision log; mention an accepted decision only when the current question depends on it.

<question-template>
```md
## Question <N>

<One focused decision question?>

<Concise grounding: relevant repository evidence, dependency, or why this is the next decision. Do not repeat settled context unless it clarifies the question.>

## Recommendation

**<One best recommendation stated as a decision.>**

<Brief rationale tied to the user's goal and available project context.>

<Optional: include the following section only when one or two small adaptations would be useful.>

### Possible variations

- **<Variation 1>:** <An adaptation that preserves the recommendation.>
- **<Variation 2>:** <Another adaptation that preserves the recommendation.>
```
</question-template>

Possible variations refine the recommendation; they are not competing alternatives.
Include at most two. Do not require reasons for accepting, changing, or skipping them.

After presenting the recommendation and any variations, use the available `question` or `ask-user` tool.
Ask whether the user accepts it or has feedback. Offer both:

- **Accept recommendation**
- **Give feedback**, with custom or free-form input enabled

Do not reduce feedback to fixed choices. If no question tool is available, ask:

> Do you accept this recommendation, or do you have feedback? You can reply with any changes you want.

## Interview order

- Ask one focused decision question at a time.
- Resolve prerequisites before dependent questions.
- Inspect repository evidence instead of asking the user for facts available locally.

## Decision handling

- Give one best recommendation, not a menu of alternatives.
- Wait for acceptance or feedback before continuing.
- If feedback changes the decision, revise the recommendation and ask again.
- Record only accepted decisions; do not automatically print the full log next turn.

## Completion

When all material branches are resolved, summarize accepted decisions, dependencies, unresolved items, and artifact updates.
Keep behavior equivalent across harnesses: question-tool use is optional, and the text fallback is required.

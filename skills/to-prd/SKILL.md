---
name: to-prd
description: Turns the current conversation context into a PRD and records it as a bead (`br`) epic. Use when the user wants to create a PRD, product requirements document, feature spec, or implementation brief from the current context.
---

# To PRD

This skill takes the current conversation context and codebase understanding, synthesizes a PRD, and records the approved PRD as a beads epic.
Don't interview user for new requirements; work from what is known.
May ask confirmation on architectural choices before creating bead.

## Process

### 1. Gather context

1. Use existing conversation context first.
2. If needed, explore the repo to understand current architecture, similar features, and test patterns.
3. Reference specs, project domain vocabulary (`CONTEXT.md`), and respect relevant ADRs (`docs/adr/`). If absent, proceed silently.

### 2. Identify implementation shape

1. Sketch the major modules that would need to be built or modified.
2. Actively look for opportunities to extract deep modules that can be tested in isolation. A deep module encapsulates meaningful functionality behind a simple, testable interface that rarely changes.

### 3. Draft the PRD

1. Use the <prd-template> template.
2. Keep the PRD product-focused and durable: avoid file paths, code snippets, and transient implementation details that may go stale.

<prd-template>
## Problem

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A long, numbered list of user stories, each in the format: As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balances on my accounts, so that I can make better informed decisions about my spending.
</user-story-example>

The list should cover all functionality of the features.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built or modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do not include specific file paths or code snippets.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test: test external behavior, not implementation details
- Which modules will be tested
- Prior art for the tests, such as similar kinds of tests already present in the codebase

## Out of Scope

A description of things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

### 4. Create the beads epic

1. Create a bead epic with the PRD as the task description using `br`
2. If `br` is not installed or no beads database exists, ask the user how they want to proceed. Do not silently initialize beads unless the user asked for setup.

Recommended task shape:

- **Title**: `PRD: <short feature name>`
- **Type**: always `epic` — the PRD bead is the parent epic task that future implementation tasks can attach to
- **Priority**: infer from context; default to `2` when unclear

Write the PRD to a tmp file, then pass its contents as the description:

```bash
br create "PRD: <short feature name>" -t epic -p 2 -l prd \
  --description "$(cat /tmp/prd.md)" \
  --json
```

### 5. Report

1. Report the created epic bead ID and title to the user.
2. Explicitly mention that follow-up implementation tasks should use this bead as their parent/source epic.

---
name: to-prd
description: Turns the current conversation context into a PRD and records it as a beads (bd) task. Use when the user wants to create a PRD, product requirements document, feature spec, or implementation brief from the current context.
---

# To PRD

This skill takes the current conversation context and codebase understanding, synthesizes a PRD, and records the approved PRD as a beads task.
Do not interview the user for new requirements; work from what is already known.
You may ask for confirmation on architecture/test choices before creating the bead.

## Process

### 1. Gather context

Use the existing conversation context first. If needed, explore the repo to understand current architecture, similar features, and test patterns.

### 2. Identify implementation shape

Sketch the major modules that would need to be built or modified. Actively look for opportunities to extract deep modules that can be tested in isolation.

A deep module encapsulates meaningful functionality behind a simple, testable interface that rarely changes.

Briefly check with the user that these modules match their expectations and ask which modules they want explicitly covered by tests.
Do not broaden this into a requirements interview.

### 3. Draft the PRD

Use the template below. Keep the PRD product-focused and durable: avoid file paths, code snippets, and transient implementation details that may go stale.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A long, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balances on my accounts, so that I can make better informed decisions about my spending.
</user-story-example>

The list should cover all important aspects of the feature.

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

### 4. Create the beads task

After the user approves the PRD, create a beads task with the PRD as the task description.

Use `bd` rather than GitHub. Do not create a GitHub tracker entry unless the user explicitly asks for GitHub instead of beads.

First verify beads is available and initialized:

```bash
bd --version
bd info
```

If `bd` is not installed or no beads database exists, ask the user how they want to proceed. Do not silently initialize beads unless the user asked for setup.

Recommended task shape:

- **Title**: `PRD: <short feature name>`
- **Type**: always `epic` — the PRD bead is the parent epic task that future implementation tasks can attach to
- **Priority**: infer from context; default to `2` when unclear
- **Labels**: include `prd` if labels are supported/desired in the project

Prefer writing the PRD to a temporary file and using `--body-file` to avoid shell quoting problems:

```bash
bd create "PRD: <short feature name>" -t epic -p 2 --body-file /tmp/prd.md --json
```

If the installed `bd` version does not support `--body-file`, use stdin if supported:

```bash
bd create "PRD: <short feature name>" -t epic -p 2 --stdin --json < /tmp/prd.md
```

Then report the created epic bead ID and title to the user.
Explicitly mention that follow-up implementation tasks should use this bead as their parent/source epic.
Do not run generic session-end storage/sync commands unless project guidance or the user explicitly asks.

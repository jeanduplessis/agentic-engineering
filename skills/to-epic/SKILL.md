---
name: to-epic
description: Turns the current conversation context into a PRD and records it as an ait (`ait`) epic. Use when the user wants to create an epic, PRD, product requirements document, feature spec, or implementation brief from the current context and track it in ait.
---

# To Epic

This skill takes the current conversation context and codebase understanding, synthesizes a PRD, and records the approved PRD as an `ait` epic.
Don't interview the user for new requirements; work from what is known.
May ask confirmation on architectural choices before creating the epic.
When using `ait`, load and follow the `ait-cli` skill.

## Process

### 1. Gather context

1. Use existing conversation context first.
2. If needed, explore the repo to understand current architecture, similar features, and test patterns.
3. Reference specs, project domain vocabulary (`CONTEXT.md`), and relevant ADRs (`docs/adr/`). If absent, proceed silently.

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

### 4. Create the ait epic

1. Use `ait` as the mutation surface; do not edit `.ait/` files directly.
2. If `ait` is unavailable or no `.ait/` project exists, ask the user how to proceed. Do not silently initialize ait.
3. Create an `ait` issue with the PRD represented in structured content fields.

Recommended issue shape:

- **Title**: `PRD: <short feature name>`
- **Issue type**: always `epic` — the PRD issue is the parent epic that future implementation tasks can attach to
- **Priority**: infer from context; default to `P2` when unclear
- **Content**: map the PRD into `goal`, `context`, `what_to_build`, `user_stories`, `decisions`, `acceptance_criteria`, `verification`, `out_of_scope`, and `agent_notes` as appropriate

Create from JSON on stdin and pass an actor:

```bash
cat <<'JSON' | ait --actor agent create --stdin
{
  "title": "PRD: <short feature name>",
  "issue_type": "epic",
  "priority": "P2",
  "content": {
    "source": "to-epic PRD from current conversation context",
    "goal": "<problem and desired outcome>",
    "context": "<durable PRD context, including problem and solution>",
    "what_to_build": "<implementation shape without file paths or code snippets>",
    "user_stories": [
      {"text": "As an <actor>, I want <feature>, so that <benefit>."}
    ],
    "decisions": [
      {"id": "D1", "text": "<implementation decision>"}
    ],
    "acceptance_criteria": [
      {"text": "<observable outcome that proves the epic is complete>"}
    ],
    "verification": ["<test or validation approach>"],
    "out_of_scope": ["<explicit non-goal>"],
    "agent_notes": ["Full PRD synthesized from existing conversation context; avoid stale file-level details."]
  }
}
JSON
```

On failure, report the `ait` command, `error.code`, `error.message`, and next safe action.

### 5. Report

1. Report the created ait epic ID and title to the user.
2. Explicitly mention that follow-up implementation tasks should use this ait issue as their parent/source epic.

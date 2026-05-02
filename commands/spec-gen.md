---
description: "Generate a behavioral feature spec from the current branch"
argument-hint: "[optional context]"
---

# Generate Feature Spec from Branch

Analyze current branch changes against `main`; generate a retroactive feature spec.
Describe **what** the feature does and **how it must behave**, not implementation.

**Optional user context:** `$ARGUMENTS`

## Procedure

Follow in order; skip none.

### 1. Identify the branch and gather the diff

- Run `git rev-parse --abbrev-ref HEAD` for the current branch name.
- If the branch is `main` or `master`, stop and tell the user this command must run from a feature branch.
- Run `git merge-base main HEAD` for the common ancestor.
- Run `git diff $(git merge-base main HEAD)..HEAD` for the full diff.
- Run `git log --oneline $(git merge-base main HEAD)..HEAD` for this branch's commit history.

### 2. Read changed files in full

- Identify every added or modified file in the diff.
- Read each file's current state to understand the complete picture, not only diff hunks.
- If tests changed, read them; tests strongly signal expected behavior and edge cases.

### 3. Analyze and extract behavioral rules

Study the diff, full files, commit messages, and user context. Extract the feature's **behavioral rules**:

- What conditions trigger specific outcomes?
- What invariants are maintained?
- What are the boundaries and constraints?
- What error cases are handled, and how?
- What relationships and dependencies exist between concepts?

Focus on **observable behavior and contracts**, not code structure, variable names, function signatures, or architectural decisions.

### 4. Determine the spec name

Derive a short, lowercase, hyphenated spec name from the feature's purpose (e.g., `session-expiry`, `rate-limiting`, `user-invitation-flow`).
Describe the behavioral domain, not implementation; avoid names like `add-middleware` or `refactor-auth-module`.

### 5. Write the spec

Create `.specs/<spec-name>.md` with this structure:

```markdown
# <Feature Title>

## Status

Draft -- generated from branch `<branch-name>` on <YYYY-MM-DD>.

## Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and
"OPTIONAL" in this document are to be interpreted as described in BCP 14
[RFC 2119] [RFC 8174] only when they appear in all capitals, as shown here.

## Overview

<A concise 2-4 sentence summary of what this feature is and why it exists.>

## Rules

### <Rule Group Heading>

1. The system MUST ...
2. The system MUST NOT ...
3. ...

### <Another Rule Group Heading>

1. ...

## Error Handling

1. When ..., the system MUST ...
2. ...

## Open Questions

- <Any ambiguities or edge cases not fully determined from code alone.>
```

### Writing guidelines

Rules:
- MUST use exactly one RFC 2119 keyword per statement.
- MUST describe behavior from "the system" perspective, not a function, class, or module.
- MUST NOT reference implementation details: file/function/class/variable names, library names, or framework concepts.
- MUST be testable: readers with only the spec can write acceptance tests.
- SHOULD be grouped by logical domain (e.g., "Authentication", "Rate Limits", "Notifications"), not code location.

Sections:
- **Overview**: provide enough context to understand rules without reading code.
- **Open Questions**: include genuine ambiguity; do not fabricate certainty.

Style:
- Use plain, direct language. Prefer short sentences.
- Do not include implementation rationale, performance notes, or migration instructions.

### 6. Verify

- Re-read every rule, confirm code support, and remove any rule not traceable to the diff or current file contents.
- Confirm no implementation details leaked.
- Ensure `.specs/` exists before writing; create it if needed.

### 7. Report

Tell the user:
- Generated spec path.
- One-line feature summary.
- Number of rules written.
- Number of open questions, if any.

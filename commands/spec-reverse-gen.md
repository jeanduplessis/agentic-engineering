---
description: "Reverse-engineer a behavioral feature spec from existing code"
argument-hint: "<domain or feature>"
---

# Reverse-Engineer Feature Spec from Existing Code

Generate a retroactive feature or behavioral-domain spec from existing code. Describe **what** the feature does and **how it must behave**, not its implementation.

**Domain or feature to specify:** `$ARGUMENTS`

## Procedure

Follow steps in order; do not skip any.

### 1. Validate input

- If `$ARGUMENTS` is empty or blank, stop and tell the user:
  > Requires a domain or feature description. Usage: `/spec-reverse-gen <domain>`
  > Examples: `authentication`, `rate limiting`, `user invitation flow`, `webhook delivery`
- Otherwise, use `$ARGUMENTS` as the domain description throughout.

### 2. Explore the codebase

Use repository search to discover domain-relevant files. Complete all steps:

1. **Derive search terms.** Identify 3-5 keywords or short phrases likely in relevant source code (e.g., for "rate limiting": `rate`, `limit`, `throttle`, `quota`, `bucket`).
2. **Grep for keywords.** Search the codebase for each keyword; record every matching file.
3. **Glob for structural matches.** Search related directory/file names (e.g., `**/*rate-limit*`, `**/*throttle*`).
4. **Find related tests.** Search test files (`*.test.*`, `*.spec.*`, files under `test/`, `tests/`, `__tests__/`, `spec/`) referencing the keywords. Tests are the strongest signal for expected behavior.
5. **Read top-level structure.** Read the project root listing to orient around modules, packages, or service boundaries.
6. **Follow imports.** From initial relevant files, trace imports and dependencies to find additional files participating in the domain's behavior.
7. **Deduplicate and prioritize.**
   - Build one relevant-file list.
   - If it exceeds roughly 20 files, prioritize: core domain logic > tests > utilities and helpers > configuration and wiring.
   - If the domain appears too broad (many unrelated subsystems), tell the user and ask them to narrow scope before continuing.

### 3. Read files in full

- Read each relevant file's current state to understand the complete picture.
- Read tests first; they define expected behavior and edge cases.

### 4. Extract behavioral rules

Study file contents and domain description. Extract the feature's **behavioral rules**:

- What conditions trigger specific outcomes?
- What invariants are maintained?
- What boundaries and constraints apply?
- What error cases are handled, and how?
- What relationships and dependencies exist between concepts?

Focus on **observable behavior and contracts**, not code structure, names, signatures, or architectural decisions.

### 5. Name the spec

Derive a short, lowercase, hyphenated spec name from the feature's purpose (e.g., `session-expiry`, `rate-limiting`, `user-invitation-flow`). Describe the behavioral domain, not implementation; avoid names like `add-middleware` or `refactor-auth-module`.

### 6. Write spec

Create `.specs/<spec-name>.md` with this structure:

```markdown
# <Feature Title>

## Status

Draft -- reverse-engineered from existing code on <YYYY-MM-DD>.

## Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and
"OPTIONAL" in this document are to be interpreted as described in
BCP 14 [RFC 2119] [RFC 8174] when, and only when, they appear in all
capitals, as shown here.

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

- <Any ambiguities or edge cases that could not be fully determined from the code alone.>
```

### Writing guidelines

- Every rule MUST use exactly one RFC 2119 keyword per statement.
- Rules MUST describe behavior from "the system" perspective, not a function, class, or module.
- Rules MUST NOT reference implementation details: no file/function/class/variable/library names or framework concepts.
- Rules MUST be testable: a spec-only reader can write acceptance tests.
- Rules SHOULD be grouped by logical domain (e.g., "Authentication", "Rate Limits", "Notifications"), not code location.
- Use **Overview** to contextualize the rules without reading the code.
- Use **Open Questions** for genuine ambiguity; do not fabricate certainty.
- Keep language plain and direct. Prefer short sentences.
- Exclude implementation rationale, performance notes, and migration instructions.

### 7. Verify

- Re-read every rule; confirm analyzed code supports it. Remove any rule not traceable to the file contents.
- Confirm no implementation details leaked into the spec.
- Ensure `.specs/` exists before writing the file; create it if needed.

### 8. Report

Report:
- Generated spec path.
- One-line feature summary.
- Rule count.
- Open-question count, if any.

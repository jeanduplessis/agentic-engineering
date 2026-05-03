---
name: context
description: Create or maintain CONTEXT.md, the agent-facing domain context contract for a repository. Use when the user wants consistent terminology, canonical domain language, ambiguity detection, DDD vocabulary, context mapping, ownership boundaries, glossary creation, or terminology/context rules for agentic engineering workflows.
---

# Skill: Context

Create or update `CONTEXT.md`: the repo's agent-facing domain language and context map. Optimize for future agent behavior, not human-friendly explanation.

## Workflow

### Source

- Use the current conversation as the primary source.
- If `CONTEXT.md` exists, read it first and preserve stable canonical terms unless the conversation clearly supersedes them.
- If legacy `AGENT_LEXICON.md` exists, read it as migration input and write the updated contract to `CONTEXT.md`.
- If legacy `CONTEXT-MAP.md` exists, read it and any referenced `CONTEXT.md` files as migration/input context.
- If relevant ADRs exist in `docs/adr/`, read only those that constrain terminology, ownership, boundaries, or agent behavior.

### Extract

Capture only context that affects agent behavior, interpretation, naming, or execution:

- domain contexts, ownership boundaries, and repo locations
- domain nouns, verbs, roles, states, and workflows
- artifacts agents must name consistently in code, docs, tasks, PRDs, tests, and review output
- vague, overloaded, or unsafe terms
- one term used for multiple concepts
- multiple terms used for one concept
- relationships between domain concepts or contexts
- ADR-backed decisions that constrain naming, ownership, or boundaries

### Decide

- Choose one canonical term per concept.
- Record avoided aliases and competing names.
- Convert vague language into explicit agent rules.
- Assign concepts to contexts when ownership matters.
- Record relationships only when they affect interpretation or execution.
- Link to ADRs instead of restating architectural trade-offs.
- Flag contradictions between `CONTEXT.md`, legacy inputs, ADRs, and the conversation; do not silently choose.

### Write

- Rewrite `CONTEXT.md` completely using the template below.
- If `AGENTS.md` exists, add or update only the short pointer below.
- Do not create `AGENTS.md` solely for this pointer unless the user asks.
- Summarize key context decisions inline.

## File contracts

### `CONTEXT.md`

Local source of truth for agent-facing domain language, contexts, ownership boundaries, ambiguity decisions, and naming rules.
It replaces the legacy `CONTEXT.md` / `CONTEXT-MAP.md` split locally.

### `AGENTS.md`

If present, add or update this section only:

```md
## Domain Context

Before changing domain behavior, read `CONTEXT.md`.
Use canonical terms from `CONTEXT.md` in code, docs, task descriptions, tests, and agent outputs.
Do not introduce synonyms for existing concepts unless updating `CONTEXT.md` first.
Do not duplicate the full context contract inside `AGENTS.md`.
```

## `CONTEXT.md` template

```md
# Context

## Scope

<One or two sentences describing the product/domain this context covers.>

## Contexts

| Context | Owns | Location | Notes |
|---|---|---|---|
| **<Context name>** | <Concepts/data/behavior owned here> | <Path or area> | <Important constraints> |

If the repo has one context, use one row.

## Canonical Terms

| Term | Agent meaning | Use this when | Avoid |
|---|---|---|---|
| **<Canonical term>** | <Precise agent-facing meaning> | <When agents should use this term> | <Aliases, vague terms, or competing names to avoid> |

## Relationships

- A **<Term A>** <relationship> one or more **<Term B>**.
- A **<Term C>** belongs to exactly one **<Context>**.

## Agent Rules

- Use **<Term>** only when <constraint>.
- Do not use "<ambiguous term>" when <condition>; use **<Canonical term>** instead.
- When creating tests/tasks/docs for <area>, use vocabulary from **<Context>**.

## Ambiguities

| Ambiguous term | Problem | Canonical decision |
|---|---|---|
| <term> | <why it is ambiguous> | <what agents should use instead> |

## Context Boundaries

- **<Context A>** owns <concept/data/behavior>.
- **<Context B>** may reference <concept> by ID only.
- Cross-context communication happens via <events, APIs, queues, shared files, or another named mechanism>.

## Decision References

- `docs/adr/0001-example.md` constrains <term/context/interface>.
```

## Selection rules

- Include only behaviorally important terminology and context boundaries.
- Skip generic programming terms unless domain-specific.
- Never copy placeholder terms unless they appear in source context.
- Be opinionated: choose one canonical term and mark alternatives as avoided.
- Use file paths only to identify context ownership or where agents should look.
- Keep ADRs separate; link to them when they constrain language or boundaries.
- Do not turn `CONTEXT.md` into implementation documentation.

## Writing rules

- Prefer operational definitions over explanatory definitions.
- Keep each term definition to one sentence.
- Do not add tutorial prose or example dialogue unless the user asks.
- On reruns: add new terms, tighten vague definitions, update ambiguity decisions, and preserve stable canonical terms.
- If legacy `AGENT_LEXICON.md` exists after migration, mention it as legacy cleanup work rather than editing it.

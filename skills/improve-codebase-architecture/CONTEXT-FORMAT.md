# CONTEXT.md Format

`CONTEXT.md` is the local agent-facing domain language/context map. It replaces the upstream `CONTEXT.md` / `CONTEXT-MAP.md` split for local skills.

## Structure

```md
# Context

## Scope

<One or two sentences describing this product/domain.>

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

## Rules

- **Be opinionated.** Choose one canonical term per concept; list aliases to avoid.

- **Flag conflicts explicitly.** If a term is ambiguous, record it in `Ambiguities` with a clear resolution.

- **Keep definitions operational.** Use one sentence per term; define what agents must mean.

- **Show relationships.** Bold term names; express cardinality/ownership when it changes agent behavior.

- **Include only behaviorally important domain terms.** Skip generic programming concepts unless domain-specific.

- **Map contexts when ownership matters.** For single-context repos, keep one `Contexts` row.

- **Use file paths sparingly.** Include paths only for context ownership or agent lookup locations.

- **Keep ADRs separate.** Link to ADRs that constrain terminology, ownership, boundaries, or interface decisions.

- **Do not add tutorial prose or example dialogue** unless the user asks.

## Compatibility

- If `CONTEXT.md` exists, read it first.
- If legacy/upstream `CONTEXT-MAP.md` exists, read it and fold relevant ownership into `CONTEXT.md`.
- If legacy `AGENT_LEXICON.md` exists, read it as migration input; write updates to `CONTEXT.md`.
- If none exists, create root `CONTEXT.md` lazily when resolving the first domain term, context boundary, or ambiguity.

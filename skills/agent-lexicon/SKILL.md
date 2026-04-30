---
name: agent-lexicon
description: Extract and maintain a concise agent-facing domain lexicon from the current conversation. Use when the user wants consistent terminology, canonical terms, ambiguity detection, DDD language, domain vocabulary, agent instructions, glossary creation, or terminology rules for agentic engineering workflows.
---

# Skill: Agent Lexicon

Create or update an agent-facing terminology contract. Optimize for future agent behavior, not human-friendly explanation.

## Workflow

### Source

- Use the current conversation as the primary source.
- If `AGENT_LEXICON.md` exists, read it first.
- Preserve stable canonical terms unless the conversation clearly supersedes them.

### Extract

Capture only terms that affect agent behavior, interpretation, naming, or execution:

- domain nouns, verbs, roles, and states
- artifacts and workflows
- vague, overloaded, or unsafe terms
- one term used for multiple concepts
- multiple terms used for one concept

### Decide

- Choose one canonical term per concept.
- Record avoided aliases and competing names.
- Convert vague language into explicit agent rules.
- Add relationships only when they affect interpretation or execution.

### Write

- Rewrite `AGENT_LEXICON.md` completely using the template below.
- If `AGENTS.md` exists, add or update only the short pointer below.
- Summarize key terminology decisions inline.

## File contracts

### `AGENT_LEXICON.md`

Use this as the source of truth for terminology.

### `AGENTS.md`

If present, add or update this section only:

```md
## Terminology

Before changing domain behavior, read `AGENT_LEXICON.md`.
Use canonical terms from `AGENT_LEXICON.md` in code, docs, task descriptions, and agent outputs.
Do not introduce synonyms for existing concepts unless updating `AGENT_LEXICON.md` first.
Do not duplicate the full lexicon inside `AGENTS.md`.
```

Do not create `AGENTS.md` solely for this pointer unless the user asks.

## `AGENT_LEXICON.md` template

```md
# Agent Lexicon

## Canonical Terms

| Term | Agent meaning | Use this when | Avoid |
|---|---|---|---|
| **<Canonical term>** | <Precise agent-facing meaning> | <When the agent should use this term> | <Aliases, vague terms, or competing names to avoid> |

## Agent Rules

- Use **<Term>** only when <constraint>.
- Do not use "<ambiguous term>" when <condition>; use **<Canonical term>** instead.

## Relationships

- A **<Term A>** <relationship> one or more **<Term B>**.

## Ambiguities

| Ambiguous term | Problem | Canonical decision |
|---|---|---|
| <term> | <why it is ambiguous> | <what to use instead> |
```

## Selection rules

- Include only behaviorally important terminology.
- Skip generic programming terms unless domain-specific.
- Never copy placeholder terms unless they appear in the source conversation.
- Be opinionated: choose one canonical term and mark alternatives as avoided.

## Writing rules

- Prefer operational definitions over explanatory definitions.
- Keep each definition to one sentence.
- Do not add tutorial prose or example dialogue unless the user asks.
- On reruns: add new terms, tighten vague definitions, and update ambiguity decisions.

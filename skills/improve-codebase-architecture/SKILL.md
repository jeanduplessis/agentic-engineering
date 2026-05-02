---
name: improve-codebase-architecture
description: Find deepening opportunities in a codebase, informed by the domain language in CONTEXT.md and the decisions in docs/adr/. Use when the user wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, or make a codebase more testable and AI-navigable.
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities**: refactors that turn shallow modules into deep ones.
Optimize for testability and AI-navigability.

## Glossary

Use these terms exactly in every suggestion. Don't drift into "component," "service," "API," or "boundary." Full definitions: [LANGUAGE.md](LANGUAGE.md).

**Module** — anything with an interface and implementation: function, class, package, or slice.

**Interface** — everything a caller must know: types, invariants, error modes, ordering, config; not just the type signature.

**Implementation** — code inside.

**Depth** — leverage at the interface: much behaviour behind a small interface.
**Deep** = high leverage; **Shallow** = interface nearly as complex as implementation.

**Seam** — where an interface lives; a place behaviour can be altered without editing there. Use this, not "boundary."

**Adapter** — concrete thing satisfying an interface at a seam.

**Leverage** — what callers get from depth.

**Locality** — what maintainers get from depth: change, bugs, and knowledge concentrated in one place.

Key principles (see [LANGUAGE.md](LANGUAGE.md) for the full list):

- **Deletion test**: delete the module mentally. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it earned its keep.
- **The interface is the test surface.**
- **One adapter = hypothetical seam. Two adapters = real seam.**

This skill is _informed_ by the project's domain context: `CONTEXT.md` and any `docs/adr/`.
Domain language names good seams; ADRs record decisions not to re-litigate.
See [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md) and [ADR-FORMAT.md](ADR-FORMAT.md).

## Process

### 1. Explore

Read existing documentation first:

- `CONTEXT.md`
- Legacy/upstream `CONTEXT-MAP.md` only if present
- Relevant ADRs in `docs/adr/` and any context-scoped `docs/adr/` directories

If any files don't exist, proceed silently: don't flag absence or suggest creating them upfront.

Then use the Agent tool with `subagent_type=Explore` to walk the codebase.
Don't follow rigid heuristics; explore organically and note where you experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow**: interface nearly as complex as implementation?
- Where have pure functions been extracted just for testability, but real bugs hide in how they're called (no **locality**)?
- Where do tightly-coupled modules leak across seams?
- Which parts are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow.
Would deleting it concentrate complexity, or just move it?
A "yes, concentrates" is the signal you want.

### 2. Present candidates

Present a numbered list of deepening opportunities. For each candidate:

- **Files** — involved files/modules
- **Problem** — why current architecture causes friction
- **Solution** — plain-English change description
- **Benefits** — locality, leverage, and test improvement

**Use CONTEXT.md vocabulary for the domain, and [LANGUAGE.md](LANGUAGE.md) vocabulary for architecture.**
If `CONTEXT.md` defines "Order," say "the Order intake module" — not "the FooBarHandler," and not "the Order service."

**ADR conflicts**: if a candidate contradicts an existing ADR, surface it only when friction warrants revisiting the ADR. Mark it clearly, e.g. _"contradicts ADR-0007 — but worth reopening because…"_. Don't list every theoretical refactor an ADR forbids.

Do NOT propose interfaces yet. Ask: "Which of these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, start a grilling conversation. Walk the design tree: constraints, dependencies, deepened module shape, what sits behind the seam, and what tests survive.

Side effects happen inline as decisions crystallize:

- **Naming a deepened module after a concept not in `CONTEXT.md`?** Add the term to `CONTEXT.md` using the local context contract; see [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md). Create the file lazily.

- **Sharpening a fuzzy term during the conversation?** Update `CONTEXT.md` immediately.

- **User rejects the candidate with a load-bearing reason?** Offer an ADR: _"Want me to record this as an ADR so future architecture reviews don't re-suggest it?"_ Only offer when a future explorer needs the reason to avoid re-suggesting the same thing. Skip ephemeral reasons ("not worth it right now") and self-evident ones. See [ADR-FORMAT.md](ADR-FORMAT.md).

- **Want to explore alternative interfaces for the deepened module?** See [INTERFACE-DESIGN.md](INTERFACE-DESIGN.md).

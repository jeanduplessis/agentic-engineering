# ADR Format

ADRs live in `docs/adr/` with sequential numbers: `0001-slug.md`, `0002-slug.md`, etc.

Create `docs/adr/` lazily: only when the first ADR is needed.

## Template

```md
# {Short title of the decision}

{1-3 sentences: context, decision, and why.}
```

That's it. An ADR can be one paragraph. Value comes from recording *that* a decision was made and *why*, not filling sections.

## Optional sections

Include only when they add genuine value. Most ADRs won't need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — useful when decisions are revisited

- **Considered Options** — only when rejected alternatives are worth remembering

- **Consequences** — only when non-obvious downstream effects need calling out

## Numbering

Scan `docs/adr/` for the highest existing number; increment by one.

## When to offer an ADR

All three must be true:

1. **Hard to reverse** — meaningful cost to changing your mind later

2. **Surprising without context** — future readers will look at the code and wonder "why on earth did they do it this way?"

3. **Result of a real trade-off** — genuine alternatives existed; you picked one for specific reasons

If easy to reverse, skip it: you'll reverse it. If not surprising, nobody will wonder why. If no real
alternative existed, record nothing beyond "we did the obvious thing."

### What qualifies

- **Architectural shape.** "We're using a monorepo." "The write model is event-sourced; the read model is projected into Postgres."

- **Integration patterns between contexts.** "Ordering and Billing communicate via domain events, not synchronous HTTP."

- **Technology choices that carry lock-in.** Database, message bus, auth provider, deployment target. Not
  every library; only ones that would take a quarter to swap out.

- **Boundary and scope decisions.** "Customer data is owned by the Customer context; other contexts reference
  it by ID only." Explicit no-s are as valuable as yes-s.

- **Deliberate deviations from the obvious path.** "We're using manual SQL instead of an ORM because X."
  Anything where a reasonable reader would assume the opposite. These stop the next engineer from "fixing"
  something deliberate.

- **Constraints not visible in code.** "We can't use AWS because of compliance requirements." "Response times
  must be under 200ms because of the partner API contract."

- **Rejected alternatives when rejection is non-obvious.** If you considered GraphQL and picked REST for
  subtle reasons, record it; otherwise someone will suggest GraphQL again in six months.

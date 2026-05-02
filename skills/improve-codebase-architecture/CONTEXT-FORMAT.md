# CONTEXT.md Format

## Structure

```md
# {Context Name}

{1-2 sentence description of this context and why it exists.}

## Language

**Order**:
{Concise term definition}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account

## Relationships

- An **Order** produces one or more **Invoices**
- An **Invoice** belongs to exactly one **Customer**

## Example dialogue

> **Dev:** "When a **Customer** places an **Order**, do we create the **Invoice** immediately?"
> **Domain expert:** "No — an **Invoice** is only generated once a **Fulfillment** is confirmed."

## Flagged ambiguities

- "account" was used to mean both **Customer** and **User** — resolved: these are distinct concepts.
```

## Rules

- **Be opinionated.** For competing words for the same concept, pick the best and list aliases to avoid.

- **Flag conflicts explicitly.** If a term is ambiguous, call it out in "Flagged ambiguities" with a clear resolution.

- **Keep definitions tight.** Max one sentence. Define what it IS, not what it does.

- **Show relationships.** Use bold term names and express cardinality where obvious.

- **Only include context-specific terms.** General programming concepts (timeouts, error types, utility
  patterns) don't belong, even if heavily used. Before adding a term, ask: is this unique to this context, or
  general programming? Only unique terms belong.

- **Group terms under subheadings** when natural clusters emerge; use a flat list if all terms share one cohesive area.

- **Write an example dialogue** between dev and domain expert that shows terms interacting naturally and clarifies boundaries between related concepts.

## Single vs multi-context repos

**Single context (most repos):** One `CONTEXT.md` at the repo root.

**Multiple contexts:** A root `CONTEXT-MAP.md` lists contexts, locations, and relationships:

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md) — receives and tracks customer orders
- [Billing](./src/billing/CONTEXT.md) — generates invoices and processes payments
- [Fulfillment](./src/fulfillment/CONTEXT.md) — manages warehouse picking and shipping

## Relationships

- **Ordering → Fulfillment**: Ordering emits `OrderPlaced` events; Fulfillment consumes them to start picking
- **Fulfillment → Billing**: Fulfillment emits `ShipmentDispatched` events; Billing consumes them to generate invoices
- **Ordering ↔ Billing**: Shared types for `CustomerId` and `Money`
```

The skill infers which structure applies:

- If `CONTEXT-MAP.md` exists, read it to find contexts

- If only a root `CONTEXT.md` exists, single context

- If neither exists, create a root `CONTEXT.md` lazily when the first term is resolved

When multiple contexts exist, infer which one the current topic relates to. If unclear, ask.

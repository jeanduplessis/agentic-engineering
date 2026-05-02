# Ordering

Ordering accepts carts, turns them into Orders, reserves Inventory, and requests Payment Authorization.

## Language

**Order**:
A customer's committed request to buy items.
_Avoid_: cart, transaction

**Inventory Reservation**:
A temporary hold on stock for an Order.
_Avoid_: lock, allocation

**Payment Authorization**:
Permission from the payment processor to capture funds for an Order.
_Avoid_: charge, payment

## Relationships

- An **Order** requires one **Inventory Reservation** before fulfillment.
- An **Order** requires one **Payment Authorization** before confirmation.
- A failed **Inventory Reservation** or **Payment Authorization** rejects the **Order**.

## Example dialogue

> **Dev:** "Can an **Order** be confirmed before the **Inventory Reservation**?"
> **Domain expert:** "No. Reservation comes first so we never authorize payment for stock we cannot fulfill."

## Flagged ambiguities

- "payment" often meant both **Payment Authorization** and capture. Use **Payment Authorization** for the pre-confirmation step.

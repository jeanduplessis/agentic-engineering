import { reserveInventory } from "./inventory";
import { authorizePayment } from "./payment";
import { auditOrderStep } from "./orderAudit";

export async function submitOrder(cart: Cart, customer: Customer): Promise<OrderReceipt> {
  auditOrderStep("started", cart.id, customer.id);

  const subtotal = cart.lines.reduce((sum, line) => sum + line.priceCents * line.quantity, 0);
  const discount = cart.couponCode ? Math.floor(subtotal * 0.1) : 0;
  const tax = Math.floor((subtotal - discount) * customer.taxRate);
  const total = subtotal - discount + tax;

  const reservation = await reserveInventory(cart.lines);
  if (!reservation.ok) {
    auditOrderStep("inventory_failed", cart.id, customer.id);
    return { status: "rejected", reason: "inventory" };
  }

  const authorization = await authorizePayment(customer.paymentToken, total);
  if (!authorization.ok) {
    auditOrderStep("payment_failed", cart.id, customer.id);
    return { status: "rejected", reason: "payment" };
  }

  auditOrderStep("confirmed", cart.id, customer.id);
  return {
    status: "confirmed",
    orderId: `order_${cart.id}`,
    reservationId: reservation.id,
    authorizationId: authorization.id,
    totalCents: total
  };
}

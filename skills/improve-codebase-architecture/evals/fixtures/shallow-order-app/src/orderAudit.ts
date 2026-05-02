export function auditOrderStep(step: string, cartId: string, customerId: string): void {
  console.log(JSON.stringify({ event: "order_step", step, cartId, customerId }));
}

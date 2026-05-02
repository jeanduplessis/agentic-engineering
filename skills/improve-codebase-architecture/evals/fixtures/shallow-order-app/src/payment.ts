export async function authorizePayment(paymentToken: string, amountCents: number): Promise<AuthorizationResult> {
  const response = await fetch("https://payments.example/authorizations", {
    method: "POST",
    body: JSON.stringify({ paymentToken, amountCents })
  });
  if (!response.ok) return { ok: false };
  const body = await response.json();
  return { ok: true, id: body.authorizationId };
}

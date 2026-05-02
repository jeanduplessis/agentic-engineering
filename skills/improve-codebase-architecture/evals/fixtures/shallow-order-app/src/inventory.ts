export async function reserveInventory(lines: CartLine[]): Promise<ReservationResult> {
  const response = await fetch("https://inventory.example/reservations", {
    method: "POST",
    body: JSON.stringify({ lines })
  });
  if (!response.ok) return { ok: false };
  const body = await response.json();
  return { ok: true, id: body.reservationId };
}

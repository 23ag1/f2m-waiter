// Per-dish colour by kitchen status — official iikoWaiter scheme:
//   не отпечатано (в корзине) = синий, отпечатано = чёрный, готово = зелёный, подано = серый.
// Backend does not send a per-dish status yet, so everything defaults to "new"
// (blue) — which is exactly how iiko shows a dish that hasn't been fired.
// See STATUS-CONTRACT.md.

export type DishStatusKey = "new" | "printed" | "ready" | "served";

export interface DishStatusStyle {
  key: DishStatusKey;
  text: string;  // colour for quantity / name / price
  label: string; // status word (готовится / готово / подано …)
}

const DISH_STATUS: Record<DishStatusKey, DishStatusStyle> = {
  new:     { key: "new",     text: "text-blue-600",  label: "не отправлено" },
  printed: { key: "printed", text: "text-ink",       label: "готовится" },
  ready:   { key: "ready",   text: "text-green-600", label: "готово" },
  served:  { key: "served",  text: "text-ink-subtle", label: "подано" },
};

// Regardless of what strings the backend sends, map them here (one place).
const DISH_STATUS_MAP: Record<string, DishStatusKey> = {
  new: "new", not_printed: "new", notprinted: "new", created: "new",
  printed: "printed", print: "printed", fired: "printed", cooking: "printed", sent: "printed", kitchen: "printed",
  ready: "ready", done: "ready", cooked: "ready", prepared: "ready",
  served: "served", delivered: "served", serve: "served",
};

export function dishStatus(status?: string): DishStatusStyle {
  const key = status ? DISH_STATUS_MAP[status.trim().toLowerCase()] : undefined;
  return DISH_STATUS[key ?? "new"];
}

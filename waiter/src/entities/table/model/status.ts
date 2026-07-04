// Table (order) entity — types + status/time model.

export interface TableGuest {
  client_id: number;
  name: string;
  dish_count: number;
}

export interface ActiveTable {
  id: number;
  client_id: number;
  table_number: string;
  total_price: number;
  dish_count: number;
  dish_names: string[];
  created_at: string;
  guests: TableGuest[];
  /** Real order status from the backend (optional; falls back to time heuristic). */
  status?: string;
}

// Order lifecycle in iikoWaiter, in real progression order.
export type StatusKey = "new" | "printed" | "ready" | "served" | "precheck";

export interface TableStatus {
  key: StatusKey;
  label: string;
  text: string; // text colour class (title + label)
  dot: string;  // bg colour class for the status indicator dot
}

// Official iikoWaiter colour semantics (see STATUS-CONTRACT.md + iiko docs):
//   синий   = новый заказ, блюда не отпечатаны
//   чёрный  = блюда отпечатаны (отправлены на кухню)
//   зелёный = блюда готовы
//   серый   = блюда поданы
//   красный = напечатан пречек (заказ нельзя редактировать)
const STATUS_STYLES: Record<StatusKey, TableStatus> = {
  new:      { key: "new",      label: "Новый заказ",      text: "text-blue-600",  dot: "bg-blue-500" },
  printed:  { key: "printed",  label: "Блюда отпечатаны", text: "text-ink",       dot: "bg-gray-500" },
  ready:    { key: "ready",    label: "Блюда готовы",     text: "text-green-600", dot: "bg-green-500" },
  served:   { key: "served",   label: "Блюда поданы",     text: "text-ink-muted", dot: "bg-gray-400" },
  precheck: { key: "precheck", label: "Заказ в пречеке",  text: "text-red-500",   dot: "bg-red-500" },
};

// Maps backend `status` strings → StatusKey. Generous synonyms; edit here (one
// place) to match whatever strings the backend actually sends.
const BACKEND_STATUS_MAP: Record<string, StatusKey> = {
  // новый / не отпечатан → синий
  new: "new", created: "new", open: "new", opened: "new", sent: "new", cooking: "new", not_printed: "new", notprinted: "new",
  // отпечатан (отправлен на кухню) → чёрный
  printed: "printed", print: "printed", fired: "printed", sent_to_kitchen: "printed", kitchen: "printed",
  // готов → зелёный
  ready: "ready", done: "ready", cooked: "ready", prepared: "ready",
  // подан → серый
  served: "served", delivered: "served", serve: "served",
  // пречек напечатан → красный
  precheck: "precheck", pre_check: "precheck", bill: "precheck", bill_printed: "precheck", check: "precheck", closing: "precheck", closed: "precheck",
};

function normalizeDate(createdAt: string): Date {
  const normalized =
    createdAt.includes("Z") || createdAt.includes("+")
      ? createdAt
      : createdAt.replace(" ", "T") + "Z";
  return new Date(normalized);
}

// No backend `status` yet → show a single calm default (blue "Новый заказ / в
// работе") instead of guessing from age. Guessing by time made every old order
// glow red, which is wrong. Real colours appear the moment the backend sends
// `status` (getStatus prefers it). `createdAt` kept for a future heuristic.
function fallbackStatus(_createdAt: string): TableStatus {
  return STATUS_STYLES.new;
}

export function getStatus(table: Pick<ActiveTable, "status" | "created_at">): TableStatus {
  const real = table.status?.trim().toLowerCase();
  if (real) {
    const key = BACKEND_STATUS_MAP[real];
    if (key) return STATUS_STYLES[key];
  }
  return fallbackStatus(table.created_at);
}

// Always show the order's wall-clock time (HH:MM), never the date.
export function formatTime(createdAt: string): string {
  if (!createdAt) return "";
  const m = createdAt.match(/(\d{1,2}):(\d{2})/);
  if (m) return `${m[1].padStart(2, "0")}:${m[2]}`;
  const d = normalizeDate(createdAt);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

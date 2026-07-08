// API setup
export const API_BASE_URL = "/api/v1";

import { getCookie } from "@/shared/lib/cookies";

const getToken = () => {
    return getCookie("waiter_token") || "";
};

export async function loginWaiter(pinCode: string) {
  const res = await fetch(`${API_BASE_URL}/waiter/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin_code: pinCode }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Неверный ПИН-код");
  }
  return res.json();
}

export async function registerWaiter(restaurantPassword: string, name: string, pinCode: string) {
  const res = await fetch(`${API_BASE_URL}/waiter/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ restaurant_password: restaurantPassword, name, pin_code: pinCode }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Ошибка регистрации");
  }
  return res.json();
}

export async function scanQr(payload: string) {
  const res = await fetch(`${API_BASE_URL}/waiter/scan-qr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_payload: payload }),
  });
  if (!res.ok) throw new Error("Invalid QR Code");
  return res.json();
}

export async function getMenu() {
  const res = await fetch(`${API_BASE_URL}/waiter/menu`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load menu");
  return res.json();
}

export async function getDishDetail(dishId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/menu/${dishId}`);
  if (!res.ok) throw new Error("Failed to load dish detail");
  return res.json();
}

export async function getBasket(clientId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/basket/${clientId}`);
  if (!res.ok) throw new Error("Failed to load basket");
  return res.json();
}

export interface ModifierSelection {
  modifier_id: string;
  name: string;
  amount: number;
  group_id?: string;
}

export async function modifyBasket(clientId: number, dishId: number, delta: number, modifiers?: ModifierSelection[], comment?: string) {
  const body: Record<string, unknown> = { dish_id: dishId, delta };
  if (modifiers && modifiers.length > 0) {
    body.modifiers = modifiers;
  }
  if (comment !== undefined) {
    body.comment = comment;
  }
  const res = await fetch(`${API_BASE_URL}/waiter/basket/${clientId}/modify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to modify basket");
  return res.json();
}

export async function removeBasketDish(clientId: number, dishId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/basket/${clientId}/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_id: dishId }),
  });
  if (!res.ok) throw new Error("Failed to remove dish");
  return res.json();
}

export async function sendOrder(clientId: number, tableNumber: string) {
  const res = await fetch(`${API_BASE_URL}/waiter/order/${clientId}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({ table_number: tableNumber }),
  });
  if (!res.ok) throw new Error("Failed to send order");
  return res.json();
}

export async function printBill(clientId: number, tableNumber: string) {
  const res = await fetch(`${API_BASE_URL}/waiter/order/${clientId}/print-bill`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({ table_number: tableNumber }),
  });
  if (!res.ok) throw new Error("Failed to print bill");
  return res.json();
}

export async function getRecommendations(
  clientId: number,
  options?: { hunger?: string; allergies?: string[] }
) {
  const params = new URLSearchParams();
  if (options?.hunger) params.set("hunger", options.hunger);
  if (options?.allergies?.length) params.set("allergies", options.allergies.join(","));
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_BASE_URL}/waiter/recommendations/${clientId}${query}`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load recommendations");
  return res.json();
}

export async function getActiveTables() {
  const res = await fetch(`${API_BASE_URL}/waiter/active-tables`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load active tables");
  return res.json();
}

export async function closeTable(tableId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/table/${tableId}/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to close table");
  return res.json();
}

export async function getTableGuests(tableId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/table/${tableId}/guests`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load table guests");
  return res.json();
}

// Split one whole portion of a dish into halves shared between exactly two
// guests. target_client_ids are the two guests each getting a ½ (usually the
// source guest + one other). Backend: POST /table/{id}/split-dish.
export async function splitDish(tableId: number, sourceClientId: number, dishId: number, targetClientIds: number[]) {
  const res = await fetch(`${API_BASE_URL}/waiter/table/${tableId}/split-dish`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({ source_client_id: sourceClientId, dish_id: dishId, target_client_ids: targetClientIds }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data && data.detail) || "Не удалось разделить блюдо");
  return data;
}

// Fire ONLY the selected dishes on the kitchen as a separate course, without
// touching the rest of the order. Backend: POST /order/send_course (already live).
export async function sendDishes(tableId: number, dishIds: number[]) {
  const res = await fetch(`${API_BASE_URL}/waiter/order/send_course`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({ table_id: tableId, dish_ids: dishIds }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data && data.detail) || "Не удалось отправить блюда на кухню");
  return data;
}

export async function addGuestToTable(tableId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/table/${tableId}/add-guest`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to add guest");
  return res.json();
}

export async function removeGuestFromTable(tableId: number, clientId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/table/${tableId}/remove-guest`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({ client_id: clientId }),
  });
  if (!res.ok) throw new Error("Failed to remove guest");
  return res.json();
}

export async function getDishModifiers(dishId: number) {
  const res = await fetch(`${API_BASE_URL}/waiter/menu/${dishId}/modifiers`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load modifiers");
  return res.json();
}

export async function getStopList() {
  const res = await fetch(`${API_BASE_URL}/waiter/stop-list`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load stop-list");
  return res.json();
}

// ====== New Order Wizard ======

export async function getIikoTables() {
  const res = await fetch(`${API_BASE_URL}/waiter/iiko-tables`, {
    headers: { "waiter-token": getToken() },
  });
  if (!res.ok) throw new Error("Failed to load iiko tables");
  return res.json();
}

export async function createTableSession(
  iikoTableId: string,
  tableNumber: string,
  guestsCount: number,
  orderType: string
) {
  const res = await fetch(`${API_BASE_URL}/waiter/order/create-table-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({
      iiko_table_id: iikoTableId,
      table_number: tableNumber,
      guests_count: guestsCount,
      order_type: orderType,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create table session");
  }
  return res.json();
}

export async function sendSessionOrder(tableId: number, orderComment?: string) {
  const body: Record<string, unknown> = { table_id: tableId };
  if (orderComment) body.order_comment = orderComment;
  const res = await fetch(`${API_BASE_URL}/waiter/order/send-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to send session order");
  }
  return res.json();
}

export async function scanQrWithTable(payload: string, tableNumber: string) {
  const res = await fetch(`${API_BASE_URL}/waiter/scan-qr`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "waiter-token": getToken() },
    body: JSON.stringify({ qr_payload: payload, table_number: tableNumber }),
  });
  if (!res.ok) throw new Error("Invalid QR Code");
  return res.json();
}

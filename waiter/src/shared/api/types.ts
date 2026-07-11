// Backend wire DTOs (shapes returned by the API).

export interface ModifierInfo {
  modifier_id: string;
  name: string;
  amount: number;
}

export interface BasketItem {
  dish_id: number;
  dish_name: string;
  quantity: number;
  price: number;
  subtotal: number;
  modifiers?: ModifierInfo[];
  comment?: string;
  /** Kitchen status of this dish (optional; backend not sending it yet). */
  status?: string;
}

export interface IikoTable {
  id: string;
  name: string;
  number: number;
  section_name: string;
}

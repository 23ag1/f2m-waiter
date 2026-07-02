// Wizard-only types for the new-order flow. Dish/menu/basket types live in the
// entities layer (@/entities/menu, @/entities/dish) and are imported directly.

export interface IikoTable {
  id: string;
  name: string;
  number: number;
  section_name: string;
}

export interface GuestSlot {
  guest_id: number;
  client_id: number;
  name: string;
  slot_index: number;
  linked: boolean;
  dish_count: number;
  hunger?: string;
  allergies?: string[];
  checkedIn?: boolean;
}

export type WizardStep = "table" | "guests" | "fill" | "review";

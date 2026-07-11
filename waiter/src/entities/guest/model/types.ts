import type { BasketItem } from "@/shared/api";

export interface GuestData {
  client_id: number;
  name: string;
  mood: string;
  hunger?: string;
  basket: BasketItem[];
  total_cost: number;
  allergies?: string[];
  dislikes?: string[];
  checkedIn?: boolean;
}

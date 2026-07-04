export interface Dish {
  id: number;
  category: string;
  name: string;
  description: string;
  price: number;
  image: string | null;
}

export interface Category {
  category_name: string;
  dishes: Dish[];
}

export interface ModifierOption {
  id: string;
  name: string;
  min_amount: number;
  max_amount: number;
  default_amount: number;
  price?: number;
}

export interface ModifierGroup {
  group_id: string;
  group_name: string;
  required: boolean;
  min_selected: number;
  max_selected: number;
  options: ModifierOption[];
}

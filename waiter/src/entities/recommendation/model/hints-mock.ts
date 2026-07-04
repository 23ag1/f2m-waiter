// ─── MOCK HINTS ───────────────────────────────────────────────────────────────
// Replace getMockHints with a real API call when ready:
//   const data = await getRecommendations(clientId, hungerLevel);
//   return data.recommendations;
// ──────────────────────────────────────────────────────────────────────────────

import type { HungerLevel } from "@/shared/lib/hunger";

const _HINT_PALETTE: Array<{ border: string; bg: string; text: string }> = [
  { border: "border-sky-200",    bg: "bg-sky-50",    text: "text-sky-700" },
  { border: "border-emerald-200",bg: "bg-emerald-50",text: "text-emerald-700" },
  { border: "border-amber-200",  bg: "bg-amber-50",  text: "text-amber-700" },
  { border: "border-purple-200", bg: "bg-purple-50", text: "text-purple-700" },
  { border: "border-rose-200",   bg: "bg-rose-50",   text: "text-rose-700" },
  { border: "border-teal-200",   bg: "bg-teal-50",   text: "text-teal-700" },
  { border: "border-orange-200", bg: "bg-orange-50", text: "text-orange-700" },
  { border: "border-indigo-200", bg: "bg-indigo-50", text: "text-indigo-700" },
  { border: "border-lime-200",   bg: "bg-lime-50",   text: "text-lime-700" },
  { border: "border-pink-200",   bg: "bg-pink-50",   text: "text-pink-700" },
  { border: "border-cyan-200",   bg: "bg-cyan-50",   text: "text-cyan-700" },
  { border: "border-yellow-200", bg: "bg-yellow-50", text: "text-yellow-700" },
];

function _hintColorByName(name: string): { border: string; bg: string; text: string } {
  const n = name.toLowerCase();
  if (n.includes("горяч") || n.includes("мяс") || n.includes("стейк") || n.includes("мангал") || n.includes("птиц") || n.includes("корейск") || n.includes("стритфуд"))
    return { border: "border-red-200",    bg: "bg-red-50",    text: "text-red-600" };
  if (n.includes("суп") || n.includes("бульон") || n.includes("солянк") || n.includes("борщ"))
    return { border: "border-sky-200",    bg: "bg-sky-50",    text: "text-sky-700" };
  if (n.includes("салат"))
    return { border: "border-emerald-200",bg: "bg-emerald-50",text: "text-emerald-700" };
  if (n.includes("десерт") || n.includes("торт") || n.includes("шоколад") || n.includes("вафл"))
    return { border: "border-purple-200", bg: "bg-purple-50", text: "text-purple-700" };
  if (n.includes("закуск") || n.includes("тарелк") || n.includes("брускетт") || n.includes("карпачч"))
    return { border: "border-amber-200",  bg: "bg-amber-50",  text: "text-amber-700" };
  if (n.includes("паст") || n.includes("пицц") || n.includes("лапш"))
    return { border: "border-yellow-200", bg: "bg-yellow-50", text: "text-yellow-700" };
  if (n.includes("рыб") || n.includes("морепродукт") || n.includes("лосос") || n.includes("креветк"))
    return { border: "border-teal-200",   bg: "bg-teal-50",   text: "text-teal-700" };
  if (n.includes("напит") || n.includes("сок") || n.includes("безалкогол") || n.includes("лимонад") || n.includes("смузи"))
    return { border: "border-cyan-200",   bg: "bg-cyan-50",   text: "text-cyan-700" };
  if (n.includes("чай") || n.includes("кофе") || n.includes("капуч") || n.includes("латте"))
    return { border: "border-stone-200",  bg: "bg-stone-50",  text: "text-stone-600" };
  if (n.includes("вин") || n.includes("шампанск") || n.includes("просекк") || n.includes("каберне"))
    return { border: "border-rose-200",   bg: "bg-rose-50",   text: "text-rose-700" };
  if (n.includes("пиво") || n.includes("пив") || n.includes("бут."))
    return { border: "border-orange-200", bg: "bg-orange-50", text: "text-orange-700" };
  if (n.includes("алкогол") || n.includes("коктейл") || n.includes("лонги") || n.includes("крепк"))
    return { border: "border-indigo-200", bg: "bg-indigo-50", text: "text-indigo-700" };
  if (n.includes("детск"))
    return { border: "border-pink-200",   bg: "bg-pink-50",   text: "text-pink-700" };
  // hash fallback
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) & 0xffff;
  return _HINT_PALETTE[hash % _HINT_PALETTE.length];
}

export const CATEGORY_COLORS: Record<string, { border: string; bg: string; text: string }> = new Proxy(
  {} as Record<string, { border: string; bg: string; text: string }>,
  { get: (_, key: string) => _hintColorByName(key) }
);

export interface HintDish {
  id: number;
  name: string;
  price: number;
  tags: string[];
  category: string;
}

interface BasketItem {
  dish_id: number;
  dish_name: string;
}

// Internal dish with ingredient keywords for allergy/dislike filtering
interface CatalogDish extends HintDish {
  ingredients: string[];
}

// The 6 target categories a waiter should cover per table
const TARGET_CATEGORIES = ["Супы", "Горячее", "Салаты", "Закуски", "Напитки", "Вино"] as const;
type TargetCategory = (typeof TARGET_CATEGORIES)[number];

// Keywords to detect which target categories a basket item belongs to
const CATEGORY_KEYWORDS: Record<TargetCategory, string[]> = {
  "Супы":    ["суп", "борщ", "том ям", "солянк", "уха", "крем-суп", "похлёбк"],
  "Горячее": ["стейк", "рибай", "грудка", "шницель", "котлет", "говяд", "свинин", "утка", "ягнёнок", "отбивн", "горяч", "жарен"],
  "Салаты":  ["салат", "цезарь", "греческ", "нисуаз", "оливье", "винегрет"],
  "Закуски": ["брускетт", "вингс", "тартар", "карпачч", "закуск", "сырная тарелк", "мясная тарелк", "хумус"],
  "Напитки": ["сок", "морс", "лимонад", "чай", "кофе", "напиток", "вода", "смузи", "айс", "фреш", "медовый"],
  "Вино":    ["вино", "шампанск", "просекко", "бокал", "каберне", "совиньон", "мерло", "пино"],
};

// Category display order
const CATEGORY_ORDER = ["Горячее", "Закуски", "Бургеры", "Паста", "Рыба", "Супы", "Салаты", "Гарниры", "Десерты", "Напитки", "Вино"];

// 2 candidate dishes per category — first that passes allergy/dislike filter is used
const CATEGORY_PICKS: Record<TargetCategory, CatalogDish[]> = {
  "Супы": [
    {
      id: 2001, name: "Борщ со сметаной", price: 490, category: "Супы",
      tags: ["бестселлер"],
      ingredients: ["свёкла", "капуста", "говядина", "сметана"],
    },
    {
      id: 2002, name: "Куриный суп с лапшой", price: 420, category: "Супы",
      tags: ["домашний вкус"],
      ingredients: ["курица", "лапша", "морковь", "лук"],
    },
  ],
  "Горячее": [
    {
      id: 2010, name: "Рибай стейк", price: 2400, category: "Горячее",
      tags: ["любимое у гостей"],
      ingredients: ["говядина"],
    },
    {
      id: 2011, name: "Курица гриль", price: 990, category: "Горячее",
      tags: ["шеф рекомендует"],
      ingredients: ["курица"],
    },
  ],
  "Салаты": [
    {
      id: 2020, name: "Цезарь с курицей", price: 620, category: "Салаты",
      tags: ["бестселлер"],
      ingredients: ["курица", "салат", "пармезан", "чеснок"],
    },
    {
      id: 2021, name: "Греческий салат", price: 560, category: "Салаты",
      tags: ["классика"],
      ingredients: ["огурец", "томат", "фета", "маслины", "лук"],
    },
  ],
  "Закуски": [
    {
      id: 2030, name: "Сырная тарелка", price: 890, category: "Закуски",
      tags: ["к вину"],
      ingredients: ["сыр", "виноград", "орехи", "мёд"],
    },
    {
      id: 2031, name: "Брускетта с томатами", price: 380, category: "Закуски",
      tags: ["к любому блюду"],
      ingredients: ["хлеб", "томат", "базилик", "чеснок"],
    },
  ],
  "Напитки": [
    {
      id: 2040, name: "Апельсиновый фреш", price: 290, category: "Напитки",
      tags: ["свежевыжатый"],
      ingredients: ["апельсин"],
    },
    {
      id: 2041, name: "Домашний лимонад", price: 260, category: "Напитки",
      tags: ["авторский"],
      ingredients: ["лимон", "мята", "сахар"],
    },
  ],
  "Вино": [
    {
      id: 2050, name: "Каберне Совиньон (бокал)", price: 590, category: "Вино",
      tags: ["к мясу"],
      ingredients: ["виноград"],
    },
    {
      id: 2051, name: "Просекко (бокал)", price: 520, category: "Вино",
      tags: ["к закускам"],
      ingredients: ["виноград"],
    },
  ],
};

// Personalized picks for checked-in guests — 3 variants by hunger level
// HIGH hunger: hearty, meat-forward
const CATEGORY_PICKS_CHECKIN_HIGH: Record<TargetCategory, CatalogDish[]> = {
  "Супы": [
    { id: 1024, name: "Говяжий бульон",           price: 390,  category: "Супы",    tags: ["к мясному ужину"],    ingredients: ["говядина"] },
    { id: 1025, name: "Крем-суп из тыквы",        price: 450,  category: "Супы",    tags: ["сезонное"],           ingredients: ["тыква", "сливки"] },
  ],
  "Горячее": [
    { id: 1001, name: "Рибай стейк",              price: 2400, category: "Горячее", tags: ["высокий аппетит"],    ingredients: ["говядина"] },
    { id: 1011, name: "Утиная грудка",            price: 1890, category: "Горячее", tags: ["шеф рекомендует"],    ingredients: ["утка"] },
  ],
  "Салаты": [
    { id: 1026, name: "Цезарь с курицей",         price: 620,  category: "Салаты",  tags: ["к мясному ужину"],    ingredients: ["курица", "пармезан", "чеснок"] },
    { id: 1027, name: "Шпинатный салат",          price: 540,  category: "Салаты",  tags: ["к горячему"],         ingredients: ["шпинат", "грецкий орех", "пармезан", "груша"] },
  ],
  "Закуски": [
    { id: 1022, name: "Карпаччо из говядины",     price: 780,  category: "Закуски", tags: ["высокий аппетит"],    ingredients: ["говядина", "пармезан", "каперсы"] },
    { id: 1023, name: "Брускетта с авокадо",      price: 420,  category: "Закуски", tags: ["к горячему"],         ingredients: ["авокадо", "лайм"] },
  ],
  "Напитки": [
    { id: 1028, name: "Тёмный эль (бокал)",       price: 350,  category: "Напитки", tags: ["к стейку"],           ingredients: ["пиво"] },
    { id: 1015, name: "Медовый напиток",          price: 290,  category: "Напитки", tags: ["авторский"],          ingredients: ["мёд", "лимон", "имбирь"] },
  ],
  "Вино": [
    { id: 1029, name: "Мальбек (бокал)",          price: 650,  category: "Вино",    tags: ["к стейку"],           ingredients: ["виноград"] },
    { id: 1033, name: "Каберне Совиньон (бокал)", price: 590,  category: "Вино",    tags: ["к красному мясу"],    ingredients: ["виноград"] },
  ],
};

// MED hunger: balanced, lighter options
const CATEGORY_PICKS_CHECKIN_MED: Record<TargetCategory, CatalogDish[]> = {
  "Супы": [
    { id: 1025, name: "Крем-суп из тыквы",        price: 450, category: "Супы",    tags: ["лёгкое начало"],      ingredients: ["тыква", "сливки"] },
    { id: 1024, name: "Говяжий бульон",           price: 390, category: "Супы",    tags: ["классика"],           ingredients: ["говядина"] },
  ],
  "Горячее": [
    { id: 1021, name: "Курица гриль",             price: 990,  category: "Горячее", tags: ["шеф рекомендует"],   ingredients: ["курица"] },
    { id: 1005, name: "Лосось на гриле",          price: 1650, category: "Горячее", tags: ["средний аппетит"],   ingredients: ["лосось", "морепродукты", "рыба", "каперсы"] },
  ],
  "Салаты": [
    { id: 1008, name: "Греческий салат",          price: 560,  category: "Салаты",  tags: ["классика"],          ingredients: ["огурец", "томат", "фета", "маслины", "лук"] },
    { id: 1027, name: "Шпинатный салат",          price: 540,  category: "Салаты",  tags: ["лёгкий"],            ingredients: ["шпинат", "грецкий орех", "пармезан", "груша"] },
  ],
  "Закуски": [
    { id: 1023, name: "Брускетта с авокадо",      price: 420,  category: "Закуски", tags: ["средний аппетит"],   ingredients: ["авокадо", "лайм"] },
    { id: 1013, name: "Брускетта с томатами",     price: 380,  category: "Закуски", tags: ["к любому блюду"],    ingredients: ["хлеб", "томат", "базилик", "чеснок"] },
  ],
  "Напитки": [
    { id: 1031, name: "Домашний лимонад",         price: 260,  category: "Напитки", tags: ["авторский"],         ingredients: ["лимон", "мята", "сахар"] },
    { id: 1032, name: "Апельсиновый фреш",        price: 290,  category: "Напитки", tags: ["свежевыжатый"],      ingredients: ["апельсин"] },
  ],
  "Вино": [
    { id: 1030, name: "Совиньон Блан (бокал)",    price: 520,  category: "Вино",    tags: ["к курице и рыбе"],   ingredients: ["виноград"] },
    { id: 1034, name: "Просекко (бокал)",         price: 500,  category: "Вино",    tags: ["к закускам"],        ingredients: ["виноград"] },
  ],
};

// LOW hunger: light, small portions, no горячее (filtered by hunger logic)
const CATEGORY_PICKS_CHECKIN_LOW: Record<TargetCategory, CatalogDish[]> = {
  "Супы": [
    { id: 1025, name: "Крем-суп из тыквы",        price: 450,  category: "Супы",    tags: ["небольшая порция"],   ingredients: ["тыква", "сливки"] },
    { id: 1024, name: "Говяжий бульон",           price: 390,  category: "Супы",    tags: ["лёгкий"],             ingredients: ["говядина"] },
  ],
  "Горячее": [
    { id: 1021, name: "Курица гриль",             price: 990,  category: "Горячее", tags: ["небольшая порция"],   ingredients: ["курица"] },
    { id: 1005, name: "Лосось на гриле",          price: 1650, category: "Горячее", tags: ["небольшой аппетит"],  ingredients: ["лосось", "морепродукты", "рыба", "каперсы"] },
  ],
  "Салаты": [
    { id: 1027, name: "Шпинатный салат",          price: 540,  category: "Салаты",  tags: ["лёгкий"],             ingredients: ["шпинат", "грецкий орех", "пармезан", "груша"] },
    { id: 1008, name: "Греческий салат",          price: 560,  category: "Салаты",  tags: ["свежий"],             ingredients: ["огурец", "томат", "фета", "маслины", "лук"] },
  ],
  "Закуски": [
    { id: 1013, name: "Брускетта с томатами",     price: 380,  category: "Закуски", tags: ["небольшой аппетит"],  ingredients: ["хлеб", "томат", "базилик", "чеснок"] },
    { id: 1023, name: "Брускетта с авокадо",      price: 420,  category: "Закуски", tags: ["небольшая порция"],   ingredients: ["авокадо", "лайм"] },
  ],
  "Напитки": [
    { id: 1032, name: "Апельсиновый фреш",        price: 290,  category: "Напитки", tags: ["свежевыжатый"],       ingredients: ["апельсин"] },
    { id: 1031, name: "Домашний лимонад",         price: 260,  category: "Напитки", tags: ["авторский"],          ingredients: ["лимон", "мята", "сахар"] },
  ],
  "Вино": [
    { id: 1034, name: "Просекко (бокал)",         price: 500,  category: "Вино",    tags: ["лёгкое"],             ingredients: ["виноград"] },
    { id: 1030, name: "Совиньон Блан (бокал)",    price: 520,  category: "Вино",    tags: ["ненавязчивое"],        ingredients: ["виноград"] },
  ],
};

function detectCoveredCategories(basketItems: BasketItem[]): Set<TargetCategory> {
  const covered = new Set<TargetCategory>();
  for (const item of basketItems) {
    const name = item.dish_name.toLowerCase();
    for (const [cat, keywords] of Object.entries(CATEGORY_KEYWORDS) as [TargetCategory, string[]][]) {
      if (keywords.some((kw) => name.includes(kw))) {
        covered.add(cat);
      }
    }
  }
  return covered;
}

function isDishBlocked(dish: CatalogDish, restrictions: string[]): boolean {
  if (restrictions.length === 0) return false;
  const lower = restrictions.map((r) => r.toLowerCase());
  return dish.ingredients.some((ing) =>
    lower.some((r) => ing.toLowerCase().includes(r) || r.includes(ing.toLowerCase()))
  );
}

// Ingredients map for existing menu dishes (used to warn about basket items)
export const DISH_INGREDIENTS: Record<number, string[]> = {
  1001: ["говядина"],
  1002: ["курица"],
  1003: ["яйца", "сыр маскарпоне", "кофе"],
  1004: ["яйца", "сливки"],
  1005: ["лосось", "морепродукты", "рыба", "каперсы"],
  1006: ["бекон", "яйца", "пармезан"],
  1007: ["картофель", "трюфель"],
  1008: ["фета", "маслины", "огурец", "томат", "лук"],
  1009: ["говядина", "трюфель"],
  1010: ["морепродукты", "креветки", "грибы", "острый перец", "лемонграсс"],
  1011: ["утка"],
  1012: ["шоколад", "яйца"],
  1013: ["томат", "чеснок", "базилик"],
  1014: ["грибы", "сливки", "пармезан", "лук"],
  1015: ["мёд", "лимон", "имбирь"],
  1021: ["курица"],
  1022: ["говядина", "пармезан", "каперсы"],
  1023: ["авокадо", "лайм"],
  1024: ["говядина"],
  1025: ["тыква", "сливки"],
  1026: ["курица", "пармезан", "чеснок"],
  1027: ["шпинат", "грецкий орех", "пармезан", "груша"],
  1028: ["пиво"],
  1029: ["виноград"],
  1030: ["виноград"],
  1031: ["лимон", "мята", "сахар"],
  1032: ["апельсин"],
  1033: ["виноград"],
  1034: ["виноград"],
};

export function getMockHints(
  basketItems: BasketItem[],
  dismissedIds: Set<number> = new Set(),
  hungerLevel?: HungerLevel,
  restrictions: string[] = [], // allergies + dislikes combined
  checkedIn?: boolean,
): HintDish[] {
  const covered = detectCoveredCategories(basketItems);

  let needed = TARGET_CATEGORIES.filter((cat) => !covered.has(cat));

  // Low hunger: remove Горячее from recommendations
  if (hungerLevel === "низкий") {
    needed = needed.filter((cat) => cat !== "Горячее");
  }

  let catalog: Record<TargetCategory, CatalogDish[]>;
  if (checkedIn) {
    catalog = hungerLevel === "высокий"
      ? CATEGORY_PICKS_CHECKIN_HIGH
      : hungerLevel === "низкий"
      ? CATEGORY_PICKS_CHECKIN_LOW
      : CATEGORY_PICKS_CHECKIN_MED;
  } else {
    catalog = CATEGORY_PICKS;
  }

  const result: HintDish[] = [];
  for (const cat of needed) {
    const picks = catalog[cat].filter(
      (d) => !dismissedIds.has(d.id) && !isDishBlocked(d, restrictions)
    );
    if (picks.length > 0) {
      const { ingredients: _i, ...dish } = picks[0];
      result.push(dish);
    }
  }

  return sortByCategory(result);
}

function sortByCategory<T extends { category: string }>(items: T[]): T[] {
  return [...items].sort(
    (a, b) => (CATEGORY_ORDER.indexOf(a.category) ?? 99) - (CATEGORY_ORDER.indexOf(b.category) ?? 99),
  );
}

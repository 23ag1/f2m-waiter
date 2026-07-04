"use client";

import { getMenu } from "@/shared/api";
import type { Category, Dish } from "./types";

// Process-wide cached menu catalog. Used as the pool of same-category dishes when
// a recommendation card is swiped away and must be replaced by another dish of
// the same category. Fetched once, then reused.

let cache: Category[] | null = null;
let inflight: Promise<Category[]> | null = null;

export async function loadCatalog(): Promise<Category[]> {
  if (cache) return cache;
  if (!inflight) {
    inflight = getMenu()
      .then((data) => {
        cache = (data.menu || []) as Category[];
        return cache;
      })
      .catch(() => {
        inflight = null; // allow a retry on next call
        return [];
      });
  }
  return inflight;
}

// Pick another dish from the same category, excluding ids already used
// (in basket, currently shown, or dismissed). Returns null if none left.
export async function pickReplacement(
  category: string,
  excludeIds: Set<number>,
): Promise<Dish | null> {
  const catalog = await loadCatalog();
  const cat = catalog.find((c) => c.category_name === category);
  if (!cat) return null;
  const candidate = cat.dishes.find((d) => !excludeIds.has(d.id));
  return candidate ?? null;
}

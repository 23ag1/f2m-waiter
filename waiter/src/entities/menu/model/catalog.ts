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

// Cycle through a category's dishes: the dish AFTER `currentId` on swipe-up, the
// one BEFORE it on swipe-down, wrapping around — so the carousel never locks up
// when the pool is exhausted. `excludeIds` (e.g. dishes already in the basket)
// are skipped but the current dish stays in the ring as the cursor.
export async function pickNextInCategory(
  category: string,
  currentId: number,
  excludeIds: Set<number>,
  dir: "up" | "down" = "up",
): Promise<Dish | null> {
  const catalog = await loadCatalog();
  const cat = catalog.find((c) => c.category_name === category);
  if (!cat) return null;
  const pool = cat.dishes.filter((d) => d.id === currentId || !excludeIds.has(d.id));
  if (pool.length < 2) return null; // nothing else in this category
  const idx = pool.findIndex((d) => d.id === currentId);
  if (idx === -1) return pool.find((d) => d.id !== currentId) ?? null;
  const n = pool.length;
  const next = pool[(((idx + (dir === "up" ? 1 : -1)) % n) + n) % n];
  return next.id === currentId ? null : next;
}

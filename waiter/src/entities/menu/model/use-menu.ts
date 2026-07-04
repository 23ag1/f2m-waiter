"use client";

import { useEffect, useState } from "react";
import { getMenu, getStopList } from "@/shared/api";
import type { Category } from "./types";

/** Loads the menu + stop-list (only when `enabled`). Used by the order card's inline menu. */
export function useMenu(enabled: boolean) {
  const [menu, setMenu] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [stoppedIds, setStoppedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    Promise.all([
      getMenu().then((data) => setMenu(data.menu || [])),
      getStopList().then((data) => setStoppedIds(new Set(data.stopped_dish_ids || []))).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [enabled]);

  return { menu, loading, stoppedIds };
}

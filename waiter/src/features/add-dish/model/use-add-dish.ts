"use client";

import { useState } from "react";
import { modifyBasket, getDishModifiers } from "@/shared/api";
import type { ModifierSelection } from "@/shared/api";
import type { Dish, ModifierGroup } from "@/entities/menu";
import type { BasketItem } from "@/entities/dish";

/**
 * Adding a dish to the active guest's order, incl. the modifiers flow
 * (choose modifiers when the dish has them, otherwise add directly) and
 * editing modifiers of an existing basket item.
 */
export function useAddDish({
  getTargetClientId,
  refreshGuest,
  stoppedIds,
  showToast,
}: {
  getTargetClientId: () => number | undefined;
  refreshGuest: (cid: number) => void;
  stoppedIds: Set<number>;
  showToast: (m: string, t?: "ok" | "err") => void;
}) {
  const [modifiersDish, setModifiersDish] = useState<Dish | null>(null);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [modSelections, setModSelections] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [editingModFor, setEditingModFor] = useState<{ clientId: number; dishId: number } | null>(null);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());

  const addDirect = async (dishId: number, modifiers?: ModifierSelection[]) => {
    const cid = getTargetClientId();
    if (cid == null) return;
    try {
      await modifyBasket(cid, dishId, 1, modifiers);
      setAddedIds((prev) => new Set(prev).add(dishId));
      setTimeout(() => setAddedIds((prev) => { const n = new Set(prev); n.delete(dishId); return n; }), 600);
      await refreshGuest(cid);
    } catch (e) {
      console.error(e);
      showToast("Ошибка добавления", "err");
    }
  };

  const openForDish = async (dish: Dish) => {
    if (stoppedIds.has(dish.id)) return;
    setLoading(true);
    try {
      const data = await getDishModifiers(dish.id);
      const mods: ModifierGroup[] = data.modifiers || [];
      if (mods.length > 0) {
        setModifiersDish(dish);
        setModifierGroups(mods);
        const defaults: Record<string, number> = {};
        for (const g of mods) for (const o of g.options) defaults[o.id] = o.default_amount || 0;
        setModSelections(defaults);
      } else {
        await addDirect(dish.id);
      }
    } catch {
      await addDirect(dish.id);
    } finally {
      setLoading(false);
    }
  };

  const openForExisting = async (clientId: number, item: BasketItem) => {
    setLoading(true);
    try {
      const data = await getDishModifiers(item.dish_id);
      const mods: ModifierGroup[] = data.modifiers || [];
      if (mods.length === 0) { showToast("Нет модификаторов"); return; }
      setModifiersDish({ id: item.dish_id, name: item.dish_name, category: "", description: "", price: item.price, image: null });
      setModifierGroups(mods);
      setEditingModFor({ clientId, dishId: item.dish_id });
      const sel: Record<string, number> = {};
      for (const g of mods) for (const o of g.options) {
        const existing = item.modifiers?.find((m) => m.modifier_id === o.id);
        sel[o.id] = existing ? existing.amount : (o.default_amount || 0);
      }
      setModSelections(sel);
    } catch {
      showToast("Ошибка загрузки модификаторов", "err");
    } finally {
      setLoading(false);
    }
  };

  const close = () => { setModifiersDish(null); setModifierGroups([]); setModSelections({}); setEditingModFor(null); };

  const confirm = async () => {
    if (!modifiersDish) return;
    const mods: ModifierSelection[] = [];
    for (const g of modifierGroups) for (const o of g.options) {
      const amount = modSelections[o.id] || 0;
      if (amount > 0) mods.push({ modifier_id: o.id, name: o.name, amount, group_id: g.group_id });
    }
    if (editingModFor) {
      await modifyBasket(editingModFor.clientId, editingModFor.dishId, 0, mods.length ? mods : undefined);
      refreshGuest(editingModFor.clientId);
    } else {
      await addDirect(modifiersDish.id, mods.length ? mods : undefined);
    }
    close();
  };

  return { modifiersDish, modifierGroups, modSelections, setModSelections, loading, editingModFor, addedIds, openForDish, openForExisting, confirm, close };
}

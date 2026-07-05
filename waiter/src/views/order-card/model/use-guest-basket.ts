"use client";

import { useEffect, useState } from "react";
import { getBasket, modifyBasket, removeBasketDish, getRecommendations } from "@/shared/api";
import { fetchRealHints, type HintDish, type Recommendation } from "@/entities/recommendation";
import { pickNextInCategory } from "@/entities/menu";
import type { BasketItem } from "@/entities/dish";
import type { HungerLevel } from "@/shared/lib/hunger";

/**
 * View model for a single-client basket (scan / menu-add flow, no table).
 * Owns the basket, its recommendations and inline hints plus the mutations
 * that used to live in the single-guest branch of the order-card view.
 */
export function useGuestBasket(clientId: number, showToast: (m: string, t?: "ok" | "err") => void) {
  const [basket, setBasket] = useState<BasketItem[]>([]);
  const [totalCost, setTotalCost] = useState(0);
  const [hunger, setHunger] = useState<HungerLevel | undefined>(undefined);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [hints, setHints] = useState<HintDish[]>([]);
  const [loading, setLoading] = useState(true);

  const loadBasket = () => {
    getBasket(clientId)
      .then((data) => {
        const items = data.basket || [];
        setBasket(items);
        setTotalCost(data.total_cost || 0);
        setHunger(data.hunger as HungerLevel | undefined);
        fetchRealHints(clientId, { hunger: data.hunger }).then(setHints);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const loadRecommendations = () => {
    getRecommendations(clientId)
      .then((data) => setRecommendations(data.recommendations || []))
      .catch(console.error);
  };

  useEffect(() => {
    loadBasket();
    loadRecommendations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  const modify = async (dishId: number, delta: number) => {
    try {
      await modifyBasket(clientId, dishId, delta);
      loadBasket();
    } catch (e) {
      console.error(e);
      showToast("Ошибка изменения", "err");
    }
  };

  const remove = async (dishId: number) => {
    try {
      await removeBasketDish(clientId, dishId);
      loadBasket();
    } catch (e) {
      console.error(e);
      showToast("Ошибка удаления", "err");
    }
  };

  const addRecommendation = async (rec: Recommendation) => {
    if (!rec.id) return;
    try {
      await modifyBasket(clientId, rec.id, 1);
      loadBasket();
      setRecommendations((prev) => prev.filter((r) => r.id !== rec.id));
    } catch (e) {
      console.error(e);
      showToast("Ошибка добавления", "err");
    }
  };

  const addHintLocally = (hint: HintDish) => {
    setBasket((prev) => {
      const existing = prev.find((i) => i.dish_id === hint.id);
      const updated = existing
        ? prev.map((i) => (i.dish_id === hint.id ? { ...i, quantity: i.quantity + 1, subtotal: Number(i.subtotal) + Number(hint.price) } : i))
        : [...prev, { dish_id: hint.id, dish_name: hint.name, quantity: 1, price: Number(hint.price), subtotal: Number(hint.price) }];
      fetchRealHints(clientId, { hunger }).then(setHints);
      return updated;
    });
  };

  // Swipe → cycle to the next/previous dish of the same category (wraps around).
  const replaceHint = async (hint: HintDish, dir: "up" | "down"): Promise<HintDish | null> => {
    const exclude = new Set<number>(basket.map((i) => i.dish_id));
    const rep = await pickNextInCategory(hint.category, hint.id, exclude, dir);
    if (!rep) return null;
    return { id: rep.id, name: rep.name, price: Number(rep.price), tags: [], category: rep.category };
  };

  return {
    basket, totalCost, hunger, recommendations, hints, loading,
    modify, remove, addRecommendation, addHintLocally, replaceHint,
  };
}

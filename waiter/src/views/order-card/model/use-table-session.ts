"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getBasket, getTableGuests, addGuestToTable, removeGuestFromTable } from "@/shared/api";
import { fetchRealHints, type HintDish } from "@/entities/recommendation";
import { pickReplacement } from "@/entities/menu";
import { nextLoyaltyProfile, type GuestData } from "@/entities/guest";
import type { BasketItem } from "@/entities/dish";

const restrictions = (g: GuestData): string[] => [...(g.allergies ?? []), ...(g.dislikes ?? [])];

/**
 * Aggregate model for a table order: its guests, their baskets, per-guest
 * recommendations, loading flags and all guest mutations. Owns the multi-guest
 * orchestration that used to live directly in the order-card view.
 */
export function useTableSession(
  tableId: string | null,
  { setLoading, showToast }: { setLoading: (v: boolean) => void; showToast: (m: string, t?: "ok" | "err") => void },
) {
  const [guests, setGuests] = useState<GuestData[]>([]);
  const [guestBaskets, setGuestBaskets] = useState<Record<number, BasketItem[]>>({});
  const [basketsLoading, setBasketsLoading] = useState<Record<number, boolean>>({});
  const [guestHints, setGuestHints] = useState<Record<number, HintDish[]>>({});
  const [guestDismissed, setGuestDismissed] = useState<Record<number, Set<number>>>({});
  const [activeGuestIdx, setActiveGuestIdx] = useState(0);
  // Dishes already surfaced as replacements per guest — avoids repeats/duplicates.
  const usedHintIds = useRef<Record<number, Set<number>>>({});

  const loadGuestBasket = useCallback(async (cid: number, hunger?: string, restr: string[] = [], checkedIn?: boolean) => {
    setBasketsLoading((prev) => ({ ...prev, [cid]: true }));
    try {
      const data = await getBasket(cid);
      const items: BasketItem[] = data.basket || [];
      setGuestBaskets((prev) => ({ ...prev, [cid]: items }));
      fetchRealHints(cid, { hunger, allergies: restr, checkedIn }).then((hints) => setGuestHints((ph) => ({ ...ph, [cid]: hints })));
    } catch {
      setGuestBaskets((prev) => ({ ...prev, [cid]: [] }));
    } finally {
      setBasketsLoading((prev) => ({ ...prev, [cid]: false }));
    }
  }, []);

  const load = useCallback(async () => {
    if (!tableId) return;
    try {
      const data = await getTableGuests(Number(tableId));
      if (data.guests && data.guests.length > 0) {
        setGuests(data.guests);
        for (const g of data.guests) loadGuestBasket(g.client_id, g.hunger, restrictions(g), g.checkedIn);
      }
    } catch (e) {
      console.error("Failed to load guests", e);
    } finally {
      setLoading(false);
    }
  }, [tableId, loadGuestBasket, setLoading]);

  useEffect(() => { load(); }, [load]);

  const refreshGuest = async (cid: number) => {
    const data = await getBasket(cid);
    const items: BasketItem[] = data.basket || [];
    setGuestBaskets((prev) => ({ ...prev, [cid]: items }));
    setGuests((prev) =>
      prev.map((g) => {
        if (g.client_id !== cid) return g;
        fetchRealHints(cid, { hunger: g.hunger, allergies: restrictions(g), checkedIn: g.checkedIn }).then((hints) => setGuestHints((ph) => ({ ...ph, [cid]: hints })));
        return { ...g, basket: items, total_cost: items.reduce((s, i) => s + Number(i.subtotal), 0) };
      }),
    );
    setGuestDismissed((prev) => ({ ...prev, [cid]: new Set() }));
  };

  const setGuestHunger = (cid: number, level: string) => {
    setGuests((prev) => {
      const updated = prev.map((g) => (g.client_id !== cid ? g : { ...g, hunger: level }));
      const g = updated.find((x) => x.client_id === cid);
      fetchRealHints(cid, { hunger: level, allergies: g ? restrictions(g) : [], checkedIn: g?.checkedIn }).then((hints) => setGuestHints((ph) => ({ ...ph, [cid]: hints })));
      return updated;
    });
  };

  const addHintDishLocally = (cid: number, hint: HintDish, hunger?: string, restr: string[] = [], checkedIn?: boolean) => {
    setGuestBaskets((prev) => {
      const current = prev[cid] || [];
      const existing = current.find((i) => i.dish_id === hint.id);
      const updated = existing
        ? current.map((i) => (i.dish_id === hint.id ? { ...i, quantity: i.quantity + 1, subtotal: Number(i.subtotal) + Number(hint.price) } : i))
        : [...current, { dish_id: hint.id, dish_name: hint.name, quantity: 1, price: Number(hint.price), subtotal: Number(hint.price) }];
      fetchRealHints(cid, { hunger, allergies: restr, checkedIn }).then((hints) => setGuestHints((ph) => ({ ...ph, [cid]: hints })));
      return { ...prev, [cid]: updated };
    });
    setGuestDismissed((prev) => ({ ...prev, [cid]: new Set() }));
  };

  // Swipe → return another dish of the SAME category (from the menu catalog).
  // Pure: the slot owns what it displays, so we don't mutate the hint list here;
  // we just exclude everything already shown / in the basket / handed out.
  const replaceHint = async (cid: number, hint: HintDish): Promise<HintDish | null> => {
    const used = usedHintIds.current[cid] ?? new Set<number>();
    const exclude = new Set<number>([
      ...(guestHints[cid] ?? []).map((h) => h.id),
      ...(guestBaskets[cid] ?? []).map((i) => i.dish_id),
      ...used,
      hint.id,
    ]);
    const rep = await pickReplacement(hint.category, exclude);
    if (!rep) return null;
    used.add(rep.id);
    usedHintIds.current[cid] = used;
    return { id: rep.id, name: rep.name, price: Number(rep.price), tags: [], category: rep.category };
  };

  const checkin = () => {
    const profile = nextLoyaltyProfile();
    setGuests((prev) => {
      const updated = prev.map((g, idx) => (idx !== activeGuestIdx ? g : { ...g, name: profile.name, hunger: profile.hunger, allergies: profile.allergies, dislikes: profile.dislikes, checkedIn: true }));
      const g = updated[activeGuestIdx];
      if (g) fetchRealHints(g.client_id, { hunger: g.hunger, allergies: restrictions(g), checkedIn: true }).then((hints) => setGuestHints((ph) => ({ ...ph, [g.client_id]: hints })));
      return updated;
    });
  };

  const addGuest = async () => {
    if (!tableId) return;
    try {
      const res = await addGuestToTable(Number(tableId));
      const newGuest: GuestData = { client_id: res.guest.client_id, name: res.guest.name, mood: "", basket: [], total_cost: 0 };
      setGuests((prev) => [...prev, newGuest]);
      setGuestBaskets((prev) => ({ ...prev, [newGuest.client_id]: [] }));
      // New guest needs recommendations too (was missing → empty strip).
      fetchRealHints(newGuest.client_id, {}).then((hints) => setGuestHints((ph) => ({ ...ph, [newGuest.client_id]: hints })));
      setActiveGuestIdx(guests.length);
    } catch (e) {
      console.error(e);
      showToast("Ошибка добавления гостя", "err");
    }
  };

  const removeGuest = async (cid: number) => {
    if (!tableId || guests.length <= 1) { showToast("Нельзя удалить единственного гостя", "err"); return; }
    try {
      await removeGuestFromTable(Number(tableId), cid);
      setGuests((prev) => prev.filter((x) => x.client_id !== cid));
      setGuestBaskets((prev) => { const n = { ...prev }; delete n[cid]; return n; });
      if (activeGuestIdx >= guests.length - 1) setActiveGuestIdx(Math.max(0, guests.length - 2));
    } catch { showToast("Ошибка удаления гостя", "err"); }
  };

  const renameGuest = (cid: number, name: string) => {
    setGuests((prev) => prev.map((g) => (g.client_id === cid ? { ...g, name: name.trim() || g.name } : g)));
  };

  return {
    guests, guestBaskets, basketsLoading, guestHints, guestDismissed,
    activeGuestIdx, setActiveGuestIdx, setGuestDismissed,
    refreshGuest, setGuestHunger, addHintDishLocally, replaceHint, checkin, addGuest, removeGuest, renameGuest,
  };
}

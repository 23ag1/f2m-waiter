"use client";

import { useSyncExternalStore } from "react";
import { getGamification } from "@/shared/api";

// ─── Gamification: "check fullness" per guest ─────────────────────────────────
// The admin sets a weight 0-1 per menu category. The waiter sums the weights of
// the DISTINCT weighted categories a guest has, and shows a progress bar toward
// a target. When the backend endpoint (/waiter/gamification) isn't live yet, we
// fall back to keyword weights matched against the real menu category names, so
// the feature already works and is replaced seamlessly once the endpoint lands.
// ──────────────────────────────────────────────────────────────────────────────

export interface GamiTarget { key: string; weight: number }

// Canonical fallback buckets (per the contract's example weights), matched to a
// dish's real category by keyword.
const FALLBACK_BUCKETS: { key: string; weight: number; re: RegExp }[] = [
  { key: "Салат",    weight: 0.3, re: /салат/i },
  { key: "Закуска",  weight: 0.3, re: /закуск|плато|брускетт|тарелк|карпачч|хумус/i },
  { key: "Основное", weight: 0.7, re: /горяч|мяс|птиц|стейк|рыб|морепрод|паст|бургер|мангал|люля|кебаб|котлет|шницел|грудк|основ|хинкал/i },
  { key: "Десерт",   weight: 0.3, re: /десерт|торт|шокол|вафл|бискв|морож|чизкейк|брюле|sweet/i },
  { key: "Напиток",  weight: 0.2, re: /напит|сок|лимонад|коктейл|\bчай|кофе|смузи|вода|пиво|вино|алког|фреш|латте|капуч|морс/i },
];

interface Gami {
  restaurant: string;
  target: number;                              // 0 → derive from Σ weights
  coefficients: Record<string, number> | null; // null → use fallback buckets
}

let state: Gami | null = null;
let inflight: Promise<void> | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function ensureLoaded() {
  if (state || inflight) return;
  inflight = getGamification()
    .then((data: { restaurant?: string; target_per_guest?: number; coefficients?: Record<string, number> }) => {
      const coef = data?.coefficients ?? null;
      state = {
        restaurant: data?.restaurant ?? "",
        target: Number(data?.target_per_guest) || 0,
        coefficients: coef && Object.keys(coef).length ? coef : null,
      };
    })
    .catch(() => { state = { restaurant: "", target: 0, coefficients: null }; })
    .finally(() => { inflight = null; emit(); });
}

function subscribe(cb: () => void) { listeners.add(cb); ensureLoaded(); return () => { listeners.delete(cb); }; }
const getSnapshot = () => state;

export interface Gamification {
  loaded: boolean;
  restaurant: string;
  target: number;
  allTargets: GamiTarget[];
  resolve: (category: string) => GamiTarget | null;
}

export function useGamification(): Gamification {
  const g = useSyncExternalStore(subscribe, getSnapshot, () => null);

  const resolve = (category: string): GamiTarget | null => {
    if (!category) return null;
    if (g?.coefficients) {
      const w = g.coefficients[category];
      return w != null && w > 0 ? { key: category, weight: w } : null;
    }
    const b = FALLBACK_BUCKETS.find((x) => x.re.test(category));
    return b ? { key: b.key, weight: b.weight } : null;
  };

  const allTargets: GamiTarget[] = g?.coefficients
    ? Object.entries(g.coefficients).filter(([, w]) => w > 0).map(([key, weight]) => ({ key, weight }))
    : FALLBACK_BUCKETS.map(({ key, weight }) => ({ key, weight }));

  const target = g?.target && g.target > 0 ? g.target : allTargets.reduce((s, t) => s + t.weight, 0);

  return { loaded: g != null, restaurant: g?.restaurant ?? "", target, allTargets, resolve };
}

// ─── Per-guest progress ───────────────────────────────────────────────────────
export interface GuestFill {
  progress: number;   // 0..1
  missing: string[];  // weighted categories the guest doesn't have yet
  status: GamiStatus;
}
export interface GamiStatus { label: string; bar: string; text: string }

const STATUS_LOW:   GamiStatus = { label: "Заказ недособран",        bar: "bg-orange-500", text: "text-orange-600" };
const STATUS_GOOD:  GamiStatus = { label: "Хороший заказ",           bar: "bg-amber-500",  text: "text-amber-600" };
const STATUS_GREAT: GamiStatus = { label: "Отличный заказ",          bar: "bg-lime-500",   text: "text-lime-600" };
const STATUS_DONE:  GamiStatus = { label: "Супер, ты добил заказ! 🎉", bar: "bg-green-500",  text: "text-green-600" };

// Unique-category model: each weighted category counts once (rewards variety).
export function computeGuestFill(categories: string[], g: Gamification): GuestFill {
  const present = new Map<string, number>();
  for (const c of categories) {
    const t = g.resolve(c);
    if (t) present.set(t.key, t.weight);
  }
  const filled = [...present.values()].reduce((s, w) => s + w, 0);
  const progress = g.target > 0 ? Math.min(1, filled / g.target) : 0;
  const missing = g.allTargets.filter((t) => !present.has(t.key)).map((t) => t.key);
  const status = progress >= 1 ? STATUS_DONE : progress >= 0.8 ? STATUS_GREAT : progress >= 0.5 ? STATUS_GOOD : STATUS_LOW;
  return { progress, missing, status };
}

"use client";

import { useSyncExternalStore } from "react";

// ─── Recommendation settings (frontend-only, localStorage) ────────────────────
// The waiter can, from their profile, reorder the recommendation categories and
// pick a header colour per category. Both the settings screen and the live hint
// feed read this store, so it's a tiny module singleton with a React subscription.
// No backend endpoint exists for this yet — persisted locally per device.
// ──────────────────────────────────────────────────────────────────────────────

export interface RecColor {
  dot: string;    // swatch circle + header accent (solid)
  bg: string;     // card background (pastel)
  border: string; // card border
  bar: string;    // "+" button / accent (solid)
}

// The 8 selectable colours (match the picker row in the design).
export const REC_COLORS: Record<string, RecColor> = {
  rose:   { dot: "bg-rose-500",   bg: "bg-rose-100",   border: "border-rose-200",   bar: "bg-rose-500" },
  orange: { dot: "bg-orange-500", bg: "bg-orange-100", border: "border-orange-200", bar: "bg-orange-500" },
  amber:  { dot: "bg-amber-500",  bg: "bg-amber-100",  border: "border-amber-200",  bar: "bg-amber-500" },
  green:  { dot: "bg-green-500",  bg: "bg-green-100",  border: "border-green-200",  bar: "bg-green-500" },
  blue:   { dot: "bg-blue-500",   bg: "bg-blue-100",   border: "border-blue-200",   bar: "bg-blue-500" },
  violet: { dot: "bg-violet-500", bg: "bg-violet-100", border: "border-violet-200", bar: "bg-violet-500" },
  teal:   { dot: "bg-teal-500",   bg: "bg-teal-100",   border: "border-teal-200",   bar: "bg-teal-500" },
  gray:   { dot: "bg-gray-500",   bg: "bg-gray-100",   border: "border-gray-200",   bar: "bg-gray-500" },
};

export type RecColorKey = keyof typeof REC_COLORS;
export const REC_COLOR_KEYS: RecColorKey[] = ["rose", "orange", "amber", "green", "blue", "violet", "teal", "gray"];

interface RecSettings {
  order: string[];                        // category display order
  colors: Record<string, RecColorKey>;    // per-category colour override
}

const KEY = "waiter_rec_settings";

let state: RecSettings = { order: [], colors: {} };
let loaded = false;
const listeners = new Set<() => void>();

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<RecSettings>;
      state = { order: parsed.order ?? [], colors: parsed.colors ?? {} };
    }
  } catch { /* ignore corrupt storage */ }
}

function persist() {
  try { window.localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* ignore */ }
}

function emit() { listeners.forEach((l) => l()); }

// Deterministic default colour for a category name (stable across sessions).
function defaultColorKey(name: string): RecColorKey {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return REC_COLOR_KEYS[h % REC_COLOR_KEYS.length];
}

// Make sure every given category has a slot in `order` (append new ones), so the
// settings screen can list them. Colours fall back to the deterministic default.
export function ensureCategories(cats: string[]) {
  load();
  const missing = cats.filter((c) => c && !state.order.includes(c));
  if (missing.length === 0) return;
  state = { order: [...state.order, ...missing], colors: { ...state.colors } };
  persist();
  emit();
}

export function getOrder(): string[] {
  load();
  return state.order;
}

// Commit a full new order (keeps any categories not present in `order` at the end).
export function setOrder(order: string[]) {
  load();
  const rest = state.order.filter((c) => !order.includes(c));
  state = { ...state, order: [...order, ...rest] };
  persist();
  emit();
}

export function reorderCategory(from: number, to: number) {
  load();
  if (from === to || from < 0 || to < 0 || from >= state.order.length || to >= state.order.length) return;
  const order = [...state.order];
  const [moved] = order.splice(from, 1);
  order.splice(to, 0, moved);
  state = { ...state, order };
  persist();
  emit();
}

export function setCategoryColor(category: string, key: RecColorKey) {
  load();
  state = { ...state, colors: { ...state.colors, [category]: key } };
  persist();
  emit();
}

export function colorKeyFor(category: string): RecColorKey {
  load();
  return state.colors[category] ?? defaultColorKey(category);
}

export function recColorFor(category: string): RecColor {
  return REC_COLORS[colorKeyFor(category)];
}

// Sort index for a category (unknown → pushed to the end, stable).
export function categoryOrderIndex(category: string): number {
  load();
  const i = state.order.indexOf(category);
  return i === -1 ? Number.MAX_SAFE_INTEGER : i;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

function getSnapshot(): RecSettings {
  load();
  return state;
}

const SERVER_SNAPSHOT: RecSettings = { order: [], colors: {} };

// Subscribe a component to settings changes. Returns the current settings.
export function useRecSettings(): RecSettings {
  return useSyncExternalStore(subscribe, getSnapshot, () => SERVER_SNAPSHOT);
}

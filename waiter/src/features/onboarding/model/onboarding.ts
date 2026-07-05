"use client";

import { useSyncExternalStore } from "react";

// ─── Waiter onboarding tour ───────────────────────────────────────────────────
// A cross-screen coach-mark tour: dashboard → profile → recommendation settings
// → an order card. Each step anchors to a `[data-tour="..."]` element; the phase
// tells host components which overlays to force open and where to navigate.
// Runs once automatically (localStorage flag) and can be replayed from the
// "Пройти обучение" button on the new-order screen.
// ──────────────────────────────────────────────────────────────────────────────

export type TourPhase = "dashboard" | "profile" | "recset" | "order";
export type TourDemo = "drag" | "tap" | "swipe";

export interface TourStep {
  id: string;
  phase: TourPhase;
  anchor: string;              // data-tour value to point at
  text: string;
  placement: "top" | "bottom";
  demo?: TourDemo;             // optional animated affordance
}

export const TOUR_STEPS: TourStep[] = [
  { id: "avatar",        phase: "dashboard", anchor: "avatar",        text: "Настрой рекомендации под себя — начни здесь", placement: "bottom" },
  { id: "profile-rec",   phase: "profile",   anchor: "profile-rec",   text: "Открой «Настройки рекомендаций»", placement: "bottom" },
  { id: "rec-drag",      phase: "recset",    anchor: "rec-handle",    text: "Перетащите категорию за ручку, чтобы изменить порядок", placement: "bottom", demo: "drag" },
  { id: "rec-color",     phase: "recset",    anchor: "rec-dot",       text: "Нажмите на кружок, чтобы сменить цвет шапки категории", placement: "bottom", demo: "tap" },
  { id: "rec-done",      phase: "recset",    anchor: "rec-back",       text: "Всё настроено! Теперь можно начинать принимать заказы", placement: "bottom" },
  { id: "order-hints",   phase: "order",     anchor: "hint-strip",    text: "Здесь вы найдёте подсказки для гостя", placement: "bottom" },
  { id: "order-swipe",   phase: "order",     anchor: "hint-card",     text: "Свайпните карточку вверх или вниз — её заменит другое блюдо той же категории", placement: "bottom", demo: "swipe" },
  { id: "order-collapse",phase: "order",     anchor: "hint-collapse", text: "Нажмите сюда, чтобы свернуть подсказки", placement: "bottom" },
];

const DONE_KEY = "waiter_onboarding_done";

interface TourState {
  active: boolean;
  index: number;
}

let state: TourState = { active: false, index: 0 };
const listeners = new Set<() => void>();

function emit() {
  state = { ...state };
  listeners.forEach((l) => l());
}

export function hasCompletedTour(): boolean {
  if (typeof window === "undefined") return true;
  try { return window.localStorage.getItem(DONE_KEY) === "1"; } catch { return true; }
}

function markDone() {
  try { window.localStorage.setItem(DONE_KEY, "1"); } catch { /* ignore */ }
}

export function startTour() {
  state = { active: true, index: 0 };
  emit();
}

export function nextStep() {
  if (!state.active) return;
  if (state.index >= TOUR_STEPS.length - 1) { finishTour(); return; }
  state = { ...state, index: state.index + 1 };
  emit();
}

export function prevStep() {
  if (!state.active || state.index === 0) return;
  state = { ...state, index: state.index - 1 };
  emit();
}

export function finishTour() {
  state = { active: false, index: 0 };
  markDone();
  emit();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}
function getSnapshot() { return state; }
const SERVER: TourState = { active: false, index: 0 };

export function useTour(): TourState {
  return useSyncExternalStore(subscribe, getSnapshot, () => SERVER);
}

// Current phase (or null when inactive) — host components read this to force the
// right overlay open / navigate.
export function useTourPhase(): TourPhase | null {
  const s = useTour();
  return s.active ? TOUR_STEPS[s.index].phase : null;
}

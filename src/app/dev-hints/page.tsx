"use client";

// Dev preview page — renders the real basket UI with mock data, no auth needed.
// Delete this file before going to production.

import { useState } from "react";
import { getMockHints, CATEGORY_COLORS } from "@/entities/recommendation";
import type { HintDish } from "@/entities/recommendation";
import type { HungerLevel } from "@/shared/lib/hunger";

function hintColor(category: string) {
  return CATEGORY_COLORS[category] ?? { border: "border-hair", bg: "bg-surface", text: "text-ink-muted" };
}

const SCENARIOS = [
  {
    label: "Суп + хлеб",
    basket: [
      { dish_id: 1, dish_name: "Борщ", quantity: 1, price: 480, subtotal: 480 },
      { dish_id: 2, dish_name: "Хлебная корзина", quantity: 1, price: 180, subtotal: 180 },
    ],
  },
  {
    label: "Стейк + гарнир",
    basket: [
      { dish_id: 3, dish_name: "Рибай стейк", quantity: 1, price: 2400, subtotal: 2400 },
      { dish_id: 4, dish_name: "Картофель фри", quantity: 2, price: 320, subtotal: 640 },
    ],
  },
  {
    label: "Только салат",
    basket: [
      { dish_id: 5, dish_name: "Греческий салат", quantity: 1, price: 560, subtotal: 560 },
    ],
  },
  {
    label: "Пустая корзина",
    basket: [],
  },
];

export default function DevHintsPreview() {
  const [scenarioIdx, setScenarioIdx] = useState(0);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const [basket, setBasket] = useState(SCENARIOS[0].basket);
  const [toast, setToast] = useState<string | null>(null);
  const [hunger, setHunger] = useState<HungerLevel>("средний");

  const hints = getMockHints(basket, dismissed, hunger);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1500);
  };

  const switchScenario = (idx: number) => {
    setScenarioIdx(idx);
    setBasket(SCENARIOS[idx].basket);
    setDismissed(new Set());
  };

  const handleAdd = (hint: HintDish) => {
    setBasket((prev) => {
      const existing = prev.find((i) => i.dish_id === hint.id);
      if (existing) return prev.map((i) => i.dish_id === hint.id ? { ...i, quantity: i.quantity + 1, subtotal: i.subtotal + hint.price } : i);
      return [...prev, { dish_id: hint.id, dish_name: hint.name, quantity: 1, price: hint.price, subtotal: hint.price }];
    });
    setDismissed((prev) => new Set(prev).add(hint.id));
    // recompute after basket update
    showToast(`${hint.name} добавлено`);
  };

  const handleDismiss = (id: number) => {
    setDismissed((prev) => new Set(prev).add(id));
  };

  const modify = (dishId: number, delta: number) => {
    setBasket((prev) =>
      prev
        .map((i) => i.dish_id === dishId ? { ...i, quantity: i.quantity + delta, subtotal: i.subtotal + i.price * delta } : i)
        .filter((i) => i.quantity > 0)
    );
    // reset dismissed when basket changes
    setDismissed(new Set());
  };

  const total = basket.reduce((s, i) => s + i.subtotal, 0);

  return (
    <div className="min-h-screen bg-app flex flex-col pb-40">
      {/* Scenario switcher banner */}
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex flex-col gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-amber-700">🧪 DEV PREVIEW</span>
          {SCENARIOS.map((s, i) => (
            <button
              key={i}
              onClick={() => switchScenario(i)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${i === scenarioIdx ? "bg-amber-400 text-white" : "bg-surface text-amber-700 border border-amber-200"}`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-amber-700 font-medium">Аппетит:</span>
          {(["низкий", "средний", "высокий"] as HungerLevel[]).map((h) => (
            <button
              key={h}
              onClick={() => setHunger(h)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${hunger === h ? "bg-orange-500 text-white" : "bg-surface text-orange-600 border border-orange-200"}`}
            >
              {h}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Real basket page header ─── */}
      <header className="p-4 bg-surface shadow-sm flex items-center justify-between border-b border-hair-soft sticky top-[40px] z-10">
        <div className="flex items-center">
          <button className="text-ink-muted p-2 -ml-2 rounded-full hover:bg-inset">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <div className="ml-2">
            <h1 className="text-lg font-bold text-ink leading-tight">Корзина Гостя</h1>
            <p className="text-xs text-ink-muted">
              ID: 123 | Настроение: <span className="text-orange-600 font-medium">уютно</span>
              {" "}| Аппетит: <span className={`font-medium ${hunger === "высокий" ? "text-red-500" : hunger === "низкий" ? "text-blue-500" : "text-ink-muted"}`}>{hunger}</span>
            </p>
          </div>
        </div>
      </header>

      {/* ─── Real basket page body ─── */}
      <main className="flex-1 p-4 max-w-lg mx-auto w-full space-y-4">
        {basket.length === 0 ? (
          <div className="text-center py-10 bg-surface rounded-2xl border border-hair-soft mt-10 shadow-sm">
            <p className="text-ink-muted">Корзина пуста</p>
          </div>
        ) : (
          <>
            {/* Basket items */}
            <div className="space-y-2">
              {basket.map((item) => (
                <div key={item.dish_id} className="bg-surface px-3 py-2 rounded-xl shadow-sm border border-hair-soft flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-ink leading-tight truncate">{item.dish_name}</p>
                    <p className="text-xs text-ink-subtle">{item.price} ₽ × {item.quantity}</p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={() => modify(item.dish_id, -1)} className="w-7 h-7 rounded-lg bg-inset flex items-center justify-center text-ink text-sm font-bold active:scale-95 transition">-</button>
                    <span className="font-bold text-ink w-4 text-center text-sm">{item.quantity}</span>
                    <button onClick={() => modify(item.dish_id, 1)} className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center text-sm font-bold active:scale-95 transition">+</button>
                    <button onClick={() => modify(item.dish_id, -item.quantity)} className="w-7 h-7 rounded-lg flex items-center justify-center text-red-300 hover:text-red-500 transition ml-1">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* ── Hint strip: 2-row horizontal scroll, color-coded by category ── */}
            {hints.length > 0 && (
              <div className="flex overflow-x-auto gap-2 -mx-1 px-1 pb-2 scrollbar-hide mt-1">
                {hints.map((hint) => {
                  const c = hintColor(hint.category);
                  return (
                    <div key={hint.id} className={`flex-shrink-0 w-28 ${c.bg} border ${c.border} rounded-lg px-2 py-2 flex flex-col gap-1`}>
                      <div className="flex items-start justify-between gap-1">
                        <p className="text-xs font-semibold text-ink leading-tight line-clamp-2 flex-1">{hint.name}</p>
                        <button onClick={() => handleAdd(hint)} className="flex-shrink-0 w-4 h-4 rounded bg-black text-white flex items-center justify-center text-xs font-bold active:scale-90 transition">+</button>
                      </div>
                      <span className="text-xs text-ink-subtle">{hint.price} ₽</span>
                      <div className="flex gap-1 overflow-hidden">
                        {hint.tags.map((tag) => (
                          <span key={tag} className="flex-shrink-0 text-xs px-1 py-px rounded-full bg-orange-50 text-orange-600 border border-orange-100 font-medium whitespace-nowrap">{tag}</span>
                        ))}
                      </div>
                      <button onClick={() => handleDismiss(hint.id)} className="text-xs text-ink-subtle hover:text-ink-muted text-left transition">не сейчас</button>
                    </div>
                  );
                })}
              </div>
            )}

            <button className="w-full py-3 rounded-xl border-2 border-dashed border-hair text-ink-muted font-medium hover:border-black hover:text-ink transition active:scale-[0.98]">
              + Добавить ещё блюда
            </button>
          </>
        )}
      </main>

      {/* ─── Real bottom bar ─── */}
      {basket.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-surface border-t border-hair p-4 pb-8 shadow-[0_-4px_20px_rgba(0,0,0,0.05)]">
          <div className="max-w-lg mx-auto">
            <div className="flex justify-between items-center mb-4 px-2">
              <span className="text-ink-muted font-medium text-sm uppercase">Итого</span>
              <span className="text-2xl font-bold text-ink">{total} ₽</span>
            </div>
            <div className="flex space-x-3">
              <button className="flex-1 bg-surface border border-black text-ink rounded-xl py-3 font-semibold shadow-sm">Отправить</button>
              <button className="flex-1 bg-black text-white rounded-xl py-3 font-semibold shadow-md">Пречек</button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl shadow-lg text-sm font-semibold bg-green-500 text-white">
          {toast}
        </div>
      )}
    </div>
  );
}

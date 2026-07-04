"use client";

import type { IikoTable } from "../../model/types";

// Wizard step 2: choose guest count and order type (new order vs add-on).
export function GuestsStep({
  table,
  guestsCount,
  onCountChange,
  sessionLoading,
  onCreate,
}: {
  table: IikoTable;
  guestsCount: number;
  onCountChange: (n: number) => void;
  sessionLoading: boolean;
  onCreate: (orderType: "new" | "add") => void;
}) {
  return (
    <main className="flex-1 flex flex-col bg-inset">
      <div className="flex-1 p-4">
        <div className="bg-surface rounded-2xl p-5 shadow-sm mb-4">
          <p className="text-sm text-ink-muted mb-1">{table.section_name} / Стол {table.number}</p>
          <p className="text-lg font-semibold text-ink mb-4">Количество гостей</p>
          <div className="flex items-center justify-between gap-4 mt-2">
            <button onClick={() => onCountChange(Math.max(1, guestsCount - 1))} className="w-16 h-16 rounded-2xl bg-inset text-ink text-4xl font-light flex items-center justify-center active:scale-95 transition">−</button>
            <span className="text-5xl font-bold text-ink w-20 text-center tabular-nums">{guestsCount}</span>
            <button onClick={() => onCountChange(guestsCount + 1)} className="w-16 h-16 rounded-2xl bg-blue-500 text-white text-4xl font-light flex items-center justify-center active:scale-95 transition">+</button>
          </div>
        </div>
      </div>
      <div className="p-4 pb-8 flex gap-3">
        <button
          onClick={() => onCreate("add")}
          disabled={sessionLoading}
          className="flex-1 py-4 rounded-2xl bg-inset text-ink font-semibold text-sm active:scale-[0.98] disabled:opacity-50 transition"
        >
          Дозаказ
        </button>
        <button
          onClick={() => onCreate("new")}
          disabled={sessionLoading}
          className="flex-1 py-4 rounded-2xl bg-blue-500 text-white font-semibold text-sm shadow-md active:scale-[0.98] disabled:opacity-50 transition"
        >
          {sessionLoading ? "Создание..." : "Новый заказ"}
        </button>
      </div>
    </main>
  );
}

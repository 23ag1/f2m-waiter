"use client";

import { useGamification, computeGuestFill } from "../model/use-gamification";

// Per-guest "check fullness" bar. `categories` are the menu categories of the
// dishes currently in this guest's basket. Recomputes on every add/remove.
export function GuestProgressBar({ categories }: { categories: string[] }) {
  const g = useGamification();
  if (!g.loaded || categories.length === 0) return null;

  const { progress, missing, status } = computeGuestFill(categories, g);
  const pct = Math.round(progress * 100);

  return (
    <div className="px-4 py-2 bg-surface">
      <div className="flex items-center justify-between mb-1">
        <span className={`text-xs font-bold ${status.text}`}>{status.label}</span>
        <span className="text-xs font-semibold text-ink-subtle tabular-nums">{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-inset overflow-hidden">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ease-out ${status.bar}`}
          style={{ width: `${Math.max(4, pct)}%` }}
        />
      </div>
      {progress < 1 && missing.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 mt-2">
          <span className="text-[11px] text-ink-subtle">Добавьте:</span>
          {missing.map((m) => (
            <span key={m} className="text-[11px] font-semibold px-2 py-1 rounded-full bg-inset text-ink-muted border border-hair">{m}</span>
          ))}
        </div>
      )}
    </div>
  );
}

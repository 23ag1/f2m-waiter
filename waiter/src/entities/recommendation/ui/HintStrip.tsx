"use client";

import { useState } from "react";
import { RecommendationCard } from "./RecommendationCard";
import { SwipeUpDismiss } from "./SwipeUpDismiss";
import { categoryOrderIndex, recColorFor, useRecSettings } from "../model/rec-settings";
import type { HintDish } from "../model/hints-mock";

// Horizontal recommendation strip under a guest's dishes.
// - Collapsible via the header (title + chevron).
// - Cards ordered by the waiter's category order and coloured per category.
// - Swipe a card UP to dismiss it (the parent swaps in another dish of the same
//   category via onDismiss).
export function HintStrip({
  hints,
  onAdd,
  onDismiss,
}: {
  hints: HintDish[];
  onAdd: (hint: HintDish) => void;
  onDismiss?: (hint: HintDish) => void;
}) {
  useRecSettings(); // re-render on colour/order changes
  const [collapsed, setCollapsed] = useState(false);

  if (hints.length === 0) return null;

  const ordered = [...hints].sort(
    (a, b) => categoryOrderIndex(a.category) - categoryOrderIndex(b.category),
  );

  return (
    <div className="bg-inset/60 border-t border-hair-soft">
      {/* Header — tap to collapse/expand */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-1.5 px-4 py-1.5 active:opacity-70 transition"
      >
        <span className="text-xs">💡</span>
        <span className="text-[11px] font-bold text-ink-muted uppercase tracking-wide">Рекомендации гостю</span>
        <span className="ml-auto flex items-center gap-1 text-ink-subtle">
          {collapsed && <span className="text-[11px] font-semibold">{ordered.length}</span>}
          <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${collapsed ? "" : "rotate-180"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </span>
      </button>

      {!collapsed && (
        <div className="overflow-x-auto px-4 pb-2 scrollbar-hide">
          <div className="flex gap-2 w-max">
            {ordered.map((hint) => (
              <SwipeUpDismiss
                key={hint.id}
                className="w-28 h-[92px] flex-shrink-0"
                onDismiss={() => onDismiss?.(hint)}
              >
                <RecommendationCard hint={hint} color={recColorFor(hint.category)} onAdd={() => onAdd(hint)} />
              </SwipeUpDismiss>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

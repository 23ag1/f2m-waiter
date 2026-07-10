"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { RecoSlot } from "./RecoSlot";
import { categoryOrderIndex, useRecSettings } from "../model/rec-settings";
import type { HintDish } from "../model/hints-mock";

const COLLAPSE_KEY = "waiter_hints_collapsed";

// Horizontal recommendation strip under a guest's dishes.
// - Collapsible via the header (title + chevron).
// - Cards ordered by the waiter's category order and coloured per category.
// - Swipe a card UP to dismiss it (the parent swaps in another dish of the same
//   category via onDismiss).
export function HintStrip({
  hints,
  onAdd,
  onReplace,
}: {
  hints: HintDish[];
  onAdd: (hint: HintDish) => void;
  onReplace: (current: HintDish, dir: "up" | "down") => Promise<HintDish | null>;
}) {
  useRecSettings(); // re-render on colour/order changes
  const [collapsed, setCollapsed] = useState<boolean>(
    () => typeof window !== "undefined" && window.localStorage.getItem(COLLAPSE_KEY) === "1",
  );

  const toggle = () => setCollapsed((c) => {
    const next = !c;
    try { window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
    return next;
  });

  if (hints.length === 0) return null;

  const ordered = [...hints].sort(
    (a, b) => categoryOrderIndex(a.category) - categoryOrderIndex(b.category),
  );

  return (
    <div data-tour="hint-strip" className="bg-inset/60 border-t border-hair-soft">
      {/* Header — tap to collapse/expand */}
      <button
        data-tour="hint-collapse"
        onClick={toggle}
        className="w-full flex items-center gap-2 px-4 py-2 active:opacity-70 transition"
      >
        <span className="text-xs">💡</span>
        <span className="text-[11px] font-bold text-ink-muted uppercase tracking-wide">Рекомендации гостю</span>
        <span className="ml-auto flex items-center gap-1 text-ink-subtle">
          {collapsed && <span className="text-[11px] font-semibold">{ordered.length}</span>}
          <ChevronDown className={`h-4 w-4 transition-transform ${collapsed ? "" : "rotate-180"}`} strokeWidth={2.5} />
        </span>
      </button>

      {!collapsed && (
        <div className="overflow-x-auto px-4 pb-2 scrollbar-hide">
          <div className="flex gap-2 w-max">
            {ordered.map((hint, i) => (
              <RecoSlot
                key={hint.id}
                initial={hint}
                dataTour={i === 0 ? "hint-card" : undefined}
                onAdd={onAdd}
                onReplace={onReplace}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

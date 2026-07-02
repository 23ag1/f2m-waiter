"use client";

import { categoryColor } from "@/shared/lib/category-color";
import type { HintDish } from "../model/hints-mock";

export function RecommendationCard({
  hint,
  onAdd,
  onDismiss,
}: {
  hint: HintDish;
  onAdd: () => void;
  onDismiss?: () => void;
}) {
  const c = categoryColor(hint.category);
  return (
    <div className={`flex-shrink-0 w-44 ${c.bg} border ${c.border} rounded-lg px-2 py-2 flex flex-col justify-between gap-1`}>
      {/* Pastel card stays light in both themes → fixed dark text */}
      <div className="flex items-start justify-between gap-1">
        <p className="text-sm font-normal text-gray-800 leading-tight min-h-[2.5rem]">{hint.name}</p>
        <button
          onClick={(e) => { e.stopPropagation(); onAdd(); }}
          className="flex-shrink-0 w-6 h-6 rounded bg-black text-white flex items-center justify-center text-sm font-bold active:scale-90"
        >+</button>
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-semibold ${c.text}`}>{hint.category}</span>
        <span className="text-xs text-gray-500">{hint.price} ₽</span>
      </div>
      {hint.tags.length > 0 && (
        <div className="flex gap-1 overflow-hidden">
          {hint.tags.map((tag) => (
            <span key={tag} className="flex-shrink-0 text-xs px-1 py-px rounded-full bg-orange-50 text-orange-600 border border-orange-100 font-medium whitespace-nowrap">{tag}</span>
          ))}
        </div>
      )}
      {onDismiss && (
        <button
          onClick={(e) => { e.stopPropagation(); onDismiss(); }}
          className="text-xs text-gray-400 hover:text-gray-600 text-left transition"
        >не сейчас</button>
      )}
    </div>
  );
}

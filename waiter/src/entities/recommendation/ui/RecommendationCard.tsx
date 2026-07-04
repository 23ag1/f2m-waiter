"use client";

import { categoryColor } from "@/shared/lib/category-color";
import type { HintDish } from "../model/hints-mock";

// Instant-read reason: icon carries the "why" at a glance, text explains briefly.
const REASON_MAP: { match: string; icon: string; label?: string }[] = [
  { match: "вин", icon: "🍷" },
  { match: "стейк", icon: "🥩" },
  { match: "остр", icon: "🌶" },
  { match: "профил", icon: "👤", label: "любит гость" },
  { match: "бестселлер", icon: "⭐", label: "хит" },
  { match: "хит", icon: "⭐" },
  { match: "дня", icon: "🔥" },
  { match: "нов", icon: "✨" },
];

function reasonOf(hint: HintDish): { icon: string; text: string } {
  const tag = hint.tags[0];
  if (!tag) return { icon: "💡", text: "советуем" };
  const low = tag.toLowerCase();
  const r = REASON_MAP.find((x) => low.includes(x.match));
  return { icon: r?.icon ?? "💡", text: r?.label ?? tag };
}

// Recommendation card: the CARD is coloured as the dish category (colour = category,
// no category text), a reason chip is instantly readable, no price, native round "+".
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
  const reason = reasonOf(hint);
  return (
    <div className={`relative flex-shrink-0 w-28 h-[92px] rounded-xl p-2 ${c.bg} border ${c.border} flex flex-col`}>
      {onDismiss && (
        <button
          onClick={(e) => { e.stopPropagation(); onDismiss(); }}
          aria-label="Скрыть"
          className="absolute top-1 right-1 w-4 h-4 rounded-full bg-black/5 text-gray-500 flex items-center justify-center text-xs leading-none active:scale-90 transition"
        >
          ×
        </button>
      )}
      {/* reason chip — leaves room for the × so it never overlaps */}
      <span className="inline-flex items-center gap-0.5 self-start bg-white/80 rounded-full pl-1 pr-1.5 py-0.5 text-[10px] font-bold text-gray-700 max-w-[calc(100%-1.25rem)]">
        <span className="leading-none">{reason.icon}</span>
        <span className="truncate">{reason.text}</span>
      </span>
      {/* name gets the FULL width (2 lines); button sits on its own row below */}
      <p className="mt-0.5 flex-1 min-h-0 text-[12px] font-bold text-gray-900 leading-tight line-clamp-2">{hint.name}</p>
      <button
        onClick={(e) => { e.stopPropagation(); onAdd(); }}
        aria-label="Добавить"
        className={`self-end w-6 h-6 rounded-full ${c.bar} text-white flex items-center justify-center shadow-sm active:scale-90 transition`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  );
}

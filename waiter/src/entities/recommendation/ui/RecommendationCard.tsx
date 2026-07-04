"use client";

import type { RecColor } from "../model/rec-settings";
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

// Recommendation card: coloured by its category (colour configurable in the
// waiter's settings), reason chip readable at a glance, no price, native round
// "+". Dismissal is a swipe-up (handled by the parent wrapper), not a × button.
export function RecommendationCard({
  hint,
  color,
  onAdd,
}: {
  hint: HintDish;
  color: RecColor;
  onAdd: () => void;
}) {
  const reason = reasonOf(hint);
  return (
    <div className={`animate-rec-in relative w-full h-full rounded-xl p-2 ${color.bg} border ${color.border} flex flex-col`}>
      {/* reason chip */}
      <span className="inline-flex items-center gap-0.5 self-start bg-white/80 rounded-full pl-1 pr-1.5 py-0.5 text-[10px] font-bold text-gray-700 max-w-full">
        <span className="leading-none">{reason.icon}</span>
        <span className="truncate">{reason.text}</span>
      </span>
      {/* name gets the FULL width (2 lines); button sits on its own row below */}
      <p className="mt-0.5 flex-1 min-h-0 text-[12px] font-bold text-gray-900 leading-tight line-clamp-2">{hint.name}</p>
      <button
        onClick={(e) => { e.stopPropagation(); onAdd(); }}
        aria-label="Добавить"
        className={`self-end w-6 h-6 rounded-full ${color.bar} text-white flex items-center justify-center shadow-sm active:scale-90 transition`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  );
}

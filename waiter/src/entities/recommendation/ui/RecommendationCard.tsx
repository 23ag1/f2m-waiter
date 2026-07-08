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

// Recommendation card: coloured by its category (configurable in the waiter's
// settings), a reason chip readable at a glance, no price. The WHOLE card is the
// tap target to add — no "+" button — so the name gets the full height.
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
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onAdd(); }}
      aria-label={`Добавить ${hint.name}`}
      className={`w-full h-full rounded-xl p-2 ${color.bg} border ${color.border} flex flex-col gap-1 text-left active:scale-[0.97] transition`}
    >
      {/* reason chip */}
      <span className="inline-flex items-center gap-1 self-start bg-white/80 rounded-full px-2 py-1 text-[10px] font-bold text-gray-700 max-w-full">
        <span className="leading-none">{reason.icon}</span>
        <span className="truncate">{reason.text}</span>
      </span>
      {/* name fills the rest of the card */}
      <span className="flex-1 min-h-0 w-full text-[13px] font-bold text-gray-900 leading-tight line-clamp-3 overflow-hidden">{hint.name}</span>
    </button>
  );
}

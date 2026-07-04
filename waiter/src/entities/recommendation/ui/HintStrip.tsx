"use client";

import { RecommendationCard } from "./RecommendationCard";
import type { HintDish } from "../model/hints-mock";

// Horizontal recommendation strip under a guest's dishes.
export function HintStrip({
  hints,
  onAdd,
  onDismiss,
}: {
  hints: HintDish[];
  onAdd: (hint: HintDish) => void;
  onDismiss?: (id: number) => void;
}) {
  if (hints.length === 0) return null;
  return (
    <div className="overflow-x-auto px-4 py-2 bg-inset/60 border-t border-hair-soft scrollbar-hide">
      <div className="flex gap-2 w-max">
        {hints.map((hint) => (
          <RecommendationCard
            key={hint.id}
            hint={hint}
            onAdd={() => onAdd(hint)}
            onDismiss={onDismiss ? () => onDismiss(hint.id) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

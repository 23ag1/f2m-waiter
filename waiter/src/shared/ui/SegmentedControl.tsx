"use client";

export interface SegOption<T extends string> {
  value: T;
  label: string;
}

// One pill segmented control — was hand-rolled for tabs, period and theme.
//  variant="raised": track on a card (bg-inset), selected chip is raised (bg-surface + shadow).
//  variant="inset":  track on an inset/header (bg-surface), selected chip is recessed (bg-inset).
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  variant = "raised",
  size = "md",
  className = "",
}: {
  options: SegOption<T>[];
  value: T;
  onChange: (v: T) => void;
  variant?: "raised" | "inset";
  size?: "sm" | "md";
  className?: string;
}) {
  const track = variant === "raised" ? "bg-inset" : "bg-surface";
  const selected = variant === "raised" ? "bg-surface text-ink shadow-sm" : "bg-inset text-ink";
  const item = size === "sm" ? "px-4 py-2" : "flex-1 py-2";
  return (
    <div className={`flex rounded-full p-1 ${track} ${className}`}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`text-sm font-semibold rounded-full transition truncate ${item} ${
            value === o.value ? selected : "text-ink-muted"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

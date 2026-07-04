"use client";

import { useEffect, useRef, useState } from "react";
import type { HungerLevel } from "@/shared/lib/hunger";

const HUNGER_OPTIONS: { value: HungerLevel; emoji: string; label: string }[] = [
  { value: "низкий", emoji: "🍃", label: "Лёгкий" },
  { value: "средний", emoji: "🍽", label: "Умеренный" },
  { value: "высокий", emoji: "🔥", label: "Сытный" },
];

export function HungerDropdown({ value, onChange }: { value?: string; onChange: (v: HungerLevel) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const cur = HUNGER_OPTIONS.find((o) => o.value === value);
  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-inset border border-hair text-xs font-medium text-ink-muted cursor-pointer"
      >
        {cur ? `${cur.emoji} ${cur.label}` : "Голод"}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-surface border border-hair rounded-xl shadow-lg p-1 min-w-[120px]">
          {HUNGER_OPTIONS.map((o) => (
            <button
              key={o.value}
              onClick={(e) => { e.stopPropagation(); onChange(o.value); setOpen(false); }}
              className={`flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm cursor-pointer text-left ${value === o.value ? "bg-inset" : "hover:bg-inset"}`}
            >
              <span>{o.emoji}</span><span className="font-medium">{o.label}</span>
            </button>
          ))}
        </div>
      )}
    </span>
  );
}

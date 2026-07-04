"use client";

import { type ReactNode, useEffect } from "react";

export interface ContextMenuItem {
  label: string;
  icon: ReactNode;
  tone?: "danger";
  onClick: () => void;
}

// iOS/iiko-style long-press context menu: dimmed+blurred backdrop with a rounded
// popover anchored near the press point, clamped to stay on screen.
export function ContextMenu({
  anchor,
  items,
  onClose,
}: {
  anchor: { x: number; y: number };
  items: ContextMenuItem[];
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const W = 264;
  const ITEM_H = 56;
  const H = items.length * ITEM_H;
  const vw = typeof window !== "undefined" ? window.innerWidth : 390;
  const vh = typeof window !== "undefined" ? window.innerHeight : 844;

  const left = Math.min(Math.max(12, anchor.x - W / 2), vw - W - 12);
  let top = anchor.y + 12;
  if (top + H > vh - 12) top = Math.max(12, anchor.y - H - 12);

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/25 backdrop-blur-sm animate-overlay-in"
      onClick={onClose}
      onContextMenu={(e) => { e.preventDefault(); onClose(); }}
    >
      <div
        className="absolute bg-surface/95 rounded-2xl shadow-2xl ring-1 ring-black/5 overflow-hidden origin-top animate-scale-in"
        style={{ left, top, width: W }}
        onClick={(e) => e.stopPropagation()}
      >
        {items.map((it, i) => (
          <button
            key={i}
            onClick={() => { it.onClick(); onClose(); }}
            className={`w-full flex items-center gap-4 px-5 h-14 text-left active:bg-inset transition ${
              it.tone === "danger" ? "text-red-500" : "text-ink"
            } ${i > 0 ? "border-t border-hair-soft" : ""}`}
          >
            <span className={`flex-shrink-0 ${it.tone === "danger" ? "text-red-500" : "text-ink"}`}>{it.icon}</span>
            <span className="text-base font-medium">{it.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

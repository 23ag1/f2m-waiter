"use client";

import { ReactNode } from "react";

// Reusable overlay sheets — replaces the 21 hand-copied `fixed inset-0` overlays.
// Spacing follows the 4pt grid (see DESIGN-SYSTEM.md).

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button
      onClick={onClose}
      className="w-8 h-8 rounded-full bg-inset flex items-center justify-center active:scale-95 transition-transform"
      aria-label="Закрыть"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-ink-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  );
}

/**
 * Form/content sheet. `side="bottom"` slides from the bottom (default);
 * `side="top"` pins to the top so inputs stay visible above the keyboard.
 */
export function Sheet({
  open,
  onClose,
  title,
  side = "bottom",
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  side?: "bottom" | "top";
  children: ReactNode;
}) {
  if (!open) return null;
  const align = side === "top" ? "items-start" : "items-end";
  const round = side === "top" ? "rounded-b-3xl" : "rounded-t-3xl";
  const pad = side === "top" ? "pt-12 pb-6" : "pt-4 pb-8";
  return (
    <div className={`fixed inset-0 z-[60] flex ${align} bg-black/40`} onClick={onClose}>
      <div className={`bg-inset w-full ${round} px-4 ${pad}`} onClick={(e) => e.stopPropagation()}>
        {title && (
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-ink">{title}</h3>
            <CloseButton onClose={onClose} />
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

export interface SheetAction {
  label: string;
  onClick: () => void;
  tone?: "default" | "primary" | "danger";
}

/**
 * iOS-style action sheet: an optional header + a list of tappable options + Cancel.
 * Replaces the guest ⋯ / course / order-type / header ⋯ inline sheets.
 */
export function ActionSheet({
  open,
  onClose,
  header,
  actions,
  cancelLabel = "Отмена",
}: {
  open: boolean;
  onClose: () => void;
  header?: string;
  actions: SheetAction[];
  cancelLabel?: string;
}) {
  if (!open) return null;
  const tone = (t?: SheetAction["tone"]) =>
    t === "danger" ? "text-red-500" : t === "primary" ? "text-blue-500 font-semibold" : "text-blue-500";
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/40" onClick={onClose}>
      <div className="w-full p-2 pb-6" onClick={(e) => e.stopPropagation()}>
        <div className="bg-surface rounded-2xl overflow-hidden divide-y divide-hair-soft">
          {header && <div className="py-3 text-center text-sm font-semibold text-ink-muted">{header}</div>}
          {actions.map((a, i) => (
            <button
              key={i}
              onClick={() => { a.onClick(); }}
              className={`w-full py-4 text-base font-medium active:bg-inset ${tone(a.tone)}`}
            >
              {a.label}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="w-full mt-2 py-4 bg-surface rounded-2xl text-base font-semibold text-ink active:bg-inset">
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}

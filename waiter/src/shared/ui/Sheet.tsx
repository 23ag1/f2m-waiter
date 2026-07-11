"use client";

import { ReactNode } from "react";
import { CloseButton } from "./CloseButton";

// Reusable overlay sheets — replaces the 21 hand-copied `fixed inset-0` overlays.
// Spacing follows the 4pt grid (see DESIGN-SYSTEM.md).

/**
 * Form/content sheet. Always slides from the bottom (iiko-style) so every
 * popup in the app is consistent. The viewport is set to resize when the
 * keyboard opens (see app/layout.tsx), so inputs stay visible above it.
 */
export function Sheet({
  open,
  onClose,
  title,
  subtitle,
  grabber = true,
  scroll = false,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  /** Secondary line under the title (e.g. the dish name). */
  subtitle?: string;
  /** Small drag handle at the top of the panel. */
  grabber?: boolean;
  /** Cap the panel height and scroll long content (dish detail / modifier lists). */
  scroll?: boolean;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-end bg-black/40" onClick={onClose}>
      <div
        className={`bg-inset w-full rounded-t-3xl px-4 pt-4 pb-8 ${scroll ? "max-h-[80vh] overflow-y-auto" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        {grabber && <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />}
        {title && (
          <div className="flex items-start justify-between gap-3 mb-4">
            <div className="min-w-0">
              <h3 className="text-xl font-bold text-ink">{title}</h3>
              {subtitle && <p className="text-sm text-ink-muted truncate mt-1">{subtitle}</p>}
            </div>
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
    <div className="fixed inset-0 z-[60] flex items-end bg-black/40" onClick={onClose}>
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

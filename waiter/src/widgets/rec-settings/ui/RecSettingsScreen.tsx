"use client";

import { useEffect, useRef, useState } from "react";
import { BackButton } from "@/shared/ui/BackButton";
import { loadCatalog } from "@/entities/menu";
import {
  ensureCategories,
  getOrder,
  setOrder,
  setCategoryColor,
  colorKeyFor,
  useRecSettings,
  REC_COLORS,
  REC_COLOR_KEYS,
} from "@/entities/recommendation";

const ROW_H = 60; // px — keep in sync with the row height class below

// Recommendation settings: reorder categories (drag on the left) and pick each
// category's header colour (swatch row at the bottom). Order + colours drive the
// live hint strip. Persisted locally (no backend endpoint yet).
export function RecSettingsScreen({ open, onClose }: { open: boolean; onClose: () => void }) {
  useRecSettings(); // re-render on colour changes
  const [cats, setCats] = useState<string[]>([]);
  const [order, setLocalOrder] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  // Smooth reorder: the dragged row follows the finger; the others slide out of
  // the way with a transition (FLIP-style). The array is only committed on drop,
  // so nothing jumps mid-drag.
  const [drag, setDrag] = useState<{ startIndex: number; dy: number; settling?: boolean } | null>(null);
  // Suppress row transitions for the frame where the new order commits: layout
  // positions change instantly there, and transitioning the transforms back to 0
  // at the same time made rows visibly jump and re-slide.
  const [frozen, setFrozen] = useState(false);
  const startY = useRef(0);
  // The tour anchors stick to ONE category (the initial top row). Anchoring by
  // index made the spotlight jump to whatever row landed on top after a drop.
  const tourCat = useRef<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    loadCatalog().then((catalog) => {
      if (!alive) return;
      const names = catalog.map((c) => c.category_name).filter(Boolean);
      ensureCategories(names);
      setCats(names);
      const known = new Set(names);
      const base = getOrder().filter((c) => known.has(c));
      const extra = names.filter((n) => !base.includes(n));
      const initial = [...base, ...extra];
      setLocalOrder(initial);
      setSelected((s) => s ?? initial[0] ?? null);
      if (!tourCat.current) tourCat.current = initial[0] ?? null;
    });
    return () => { alive = false; };
  }, [open]);

  if (!open) return null;

  const targetIndex = drag
    ? Math.max(0, Math.min(order.length - 1, Math.round(drag.startIndex + drag.dy / ROW_H)))
    : null;

  const onDown = (e: React.PointerEvent, idx: number) => {
    if (drag?.settling) return;
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    startY.current = e.clientY;
    setSelected(null); // collapse the colour picker so rows stay uniform height
    setDrag({ startIndex: idx, dy: 0 });
  };
  const onMove = (e: React.PointerEvent) => {
    setDrag((d) => {
      if (!d || d.settling) return d;
      const maxUp = -d.startIndex * ROW_H;
      const maxDown = (order.length - 1 - d.startIndex) * ROW_H;
      const dy = Math.max(maxUp, Math.min(maxDown, e.clientY - startY.current));
      return { ...d, dy };
    });
  };
  const onUp = () => {
    if (!drag || drag.settling) return;
    const target = targetIndex ?? drag.startIndex;
    const startIndex = drag.startIndex;
    // Glide the dragged row into its target slot first, then commit the order —
    // so the row settles smoothly instead of snapping on release.
    setDrag({ startIndex, dy: (target - startIndex) * ROW_H, settling: true });
    window.setTimeout(() => {
      if (target !== startIndex) {
        const next = [...order];
        const [m] = next.splice(startIndex, 1);
        next.splice(target, 0, m);
        setLocalOrder(next);
        setOrder(next);
      }
      // Commit + transform reset land in the SAME render with transitions off,
      // so every row snaps to the exact pixels it already occupies (no re-slide).
      setFrozen(true);
      setDrag(null);
      requestAnimationFrame(() => requestAnimationFrame(() => setFrozen(false)));
    }, 190);
  };

  return (
    <div className="fixed inset-0 z-[60] bg-inset overflow-y-auto">
      <div className="px-4 pt-12 pb-1">
        <span data-tour="rec-back" className="inline-flex rounded-full">
          <BackButton onClick={onClose} />
        </span>
      </div>

      <div className="px-5 pt-2 pb-5">
        <h1 className="text-2xl font-extrabold text-ink tracking-tight leading-tight">Настройки<br />рекомендаций</h1>
        <p className="text-sm text-ink-muted mt-2">
          Порядок категорий и цвет шапки в блоке «Рекомендации гостю»
        </p>
      </div>

      {/* Reorderable list — the colour picker expands inline under the selected row */}
      <div className="px-4 pb-10">
        <div className="bg-surface rounded-2xl overflow-hidden shadow-sm divide-y divide-hair-soft">
          {order.map((cat, idx) => {
            const isDrag = drag?.startIndex === idx;
            const color = REC_COLORS[colorKeyFor(cat)];
            const isSel = selected === cat;
            const showPicker = isSel && drag === null;
            // FLIP offset: non-dragged rows between the origin and the target slide
            // one row-height to open a gap for the dragged row.
            let shift = 0;
            if (drag && !isDrag && targetIndex !== null) {
              if (targetIndex > drag.startIndex && idx > drag.startIndex && idx <= targetIndex) shift = -ROW_H;
              else if (targetIndex < drag.startIndex && idx >= targetIndex && idx < drag.startIndex) shift = ROW_H;
            }
            const translate = isDrag ? drag!.dy : shift;
            return (
              <div
                key={cat}
                className={`relative ${isDrag ? (drag?.settling ? "z-20 transition-transform duration-200 ease-out" : "z-20") : frozen ? "z-0" : "z-0 transition-transform duration-200 ease-out"}`}
                style={{ transform: `translateY(${translate}px)` }}
              >
                {/* Row */}
                <div
                  className={`relative flex items-center gap-3 px-3 ${isDrag ? "shadow-xl scale-[1.03] rounded-xl bg-surface" : ""} ${isSel && !isDrag ? "bg-inset/70" : "bg-surface"}`}
                  style={{ height: ROW_H }}
                  onClick={() => setSelected((s) => (s === cat ? null : cat))}
                >
                  {/* drag handle */}
                  <button
                    aria-label="Перетащить"
                    data-tour={cat === tourCat.current ? "rec-handle" : undefined}
                    className="shrink-0 -ml-1 p-1 text-ink-subtle touch-none cursor-grab active:cursor-grabbing"
                    onPointerDown={(e) => onDown(e, idx)}
                    onPointerMove={onMove}
                    onPointerUp={onUp}
                    onPointerCancel={onUp}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                      <circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" />
                      <circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" />
                      <circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" />
                    </svg>
                  </button>
                  <span className="flex-1 min-w-0 truncate text-[15px] font-semibold text-ink">{cat}</span>
                  {/* current colour dot — also toggles the picker */}
                  <span data-tour={cat === tourCat.current ? "rec-dot" : undefined} className={`shrink-0 w-7 h-7 rounded-full ${color.dot} transition ${isSel ? "ring-2 ring-offset-2 ring-offset-surface ring-ink/40" : ""}`} />
                </div>

                {/* Inline colour picker for this category */}
                {showPicker && (
                  <div data-tour="rec-picker" className="animate-panel-expand bg-inset/50 px-3 pt-2 pb-3">
                    <div className="flex items-center justify-between gap-1">
                      {REC_COLOR_KEYS.map((key) => {
                        const active = colorKeyFor(cat) === key;
                        return (
                          <button
                            key={key}
                            aria-label={key}
                            onClick={(e) => { e.stopPropagation(); setCategoryColor(cat, key); }}
                            className={`w-8 h-8 rounded-full flex items-center justify-center ${REC_COLORS[key].dot} active:scale-90 transition ${active ? "ring-2 ring-offset-2 ring-offset-inset ring-ink" : ""}`}
                          >
                            {active && (
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white drop-shadow" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {order.length === 0 && (
            <div className="py-10 text-center text-sm text-ink-subtle">Загрузка категорий…</div>
          )}
        </div>
        <p className="text-xs text-ink-subtle mt-3 px-1">
          Потяните <span className="font-semibold text-ink-muted">⠿</span> чтобы изменить порядок · нажмите на категорию, чтобы выбрать цвет
        </p>
      </div>
    </div>
  );
}

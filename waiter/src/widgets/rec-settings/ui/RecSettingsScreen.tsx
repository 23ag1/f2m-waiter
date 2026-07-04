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

  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragY, setDragY] = useState(0);
  const start = useRef<{ y: number; idx: number } | null>(null);

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
    });
    return () => { alive = false; };
  }, [open]);

  if (!open) return null;

  const onDown = (e: React.PointerEvent, idx: number) => {
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    start.current = { y: e.clientY, idx };
    setDragIdx(idx);
    setDragY(0);
  };
  const onMove = (e: React.PointerEvent) => {
    if (dragIdx === null || !start.current) return;
    const dy = e.clientY - start.current.y;
    const steps = Math.round(dy / ROW_H);
    const target = Math.max(0, Math.min(order.length - 1, start.current.idx + steps));
    if (target !== dragIdx) {
      setLocalOrder((prev) => {
        const next = [...prev];
        const [m] = next.splice(dragIdx, 1);
        next.splice(target, 0, m);
        return next;
      });
      setDragIdx(target);
      start.current = { y: e.clientY, idx: target };
      setDragY(0);
    } else {
      setDragY(dy);
    }
  };
  const onUp = () => {
    if (dragIdx !== null) setOrder(order);
    setDragIdx(null);
    setDragY(0);
    start.current = null;
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
            const isDrag = dragIdx === idx;
            const color = REC_COLORS[colorKeyFor(cat)];
            const isSel = selected === cat;
            const showPicker = isSel && dragIdx === null;
            return (
              <div key={cat} className={isDrag ? "relative z-10" : ""}>
                {/* Row */}
                <div
                  className={`relative flex items-center gap-3 px-3 ${isDrag ? "shadow-lg scale-[1.02] bg-surface" : "transition-transform duration-150"} ${isSel && !isDrag ? "bg-inset/70" : "bg-surface"}`}
                  style={{ height: ROW_H, transform: isDrag ? `translateY(${dragY}px)` : undefined }}
                  onClick={() => setSelected((s) => (s === cat ? null : cat))}
                >
                  {/* drag handle */}
                  <button
                    aria-label="Перетащить"
                    data-tour={idx === 0 ? "rec-handle" : undefined}
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
                  <span data-tour={idx === 0 ? "rec-dot" : undefined} className={`shrink-0 w-7 h-7 rounded-full ${color.dot} transition ${isSel ? "ring-2 ring-offset-2 ring-offset-surface ring-ink/40" : ""}`} />
                </div>

                {/* Inline colour picker for this category */}
                {showPicker && (
                  <div className="animate-panel-expand bg-inset/50 px-3 pt-2 pb-3">
                    <div className="flex items-center justify-between gap-1">
                      {REC_COLOR_KEYS.map((key) => {
                        const active = colorKeyFor(cat) === key;
                        return (
                          <button
                            key={key}
                            aria-label={key}
                            onClick={(e) => { e.stopPropagation(); setCategoryColor(cat, key); }}
                            className={`w-8 h-8 rounded-full ${REC_COLORS[key].dot} active:scale-90 transition ${active ? "ring-2 ring-offset-2 ring-offset-inset ring-ink" : ""}`}
                          />
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

"use client";

import Link from "next/link";
import { useRef } from "react";
import { Users } from "lucide-react";
import { getStatus, formatTime, type ActiveTable } from "../model/status";

const LONG_PRESS_MS = 450;
const MOVE_TOLERANCE = 10;

export function TableCard({
  table,
  nameOverride,
  onLongPress,
}: {
  table: ActiveTable;
  nameOverride?: string;
  onLongPress?: (anchor: { x: number; y: number }) => void;
}) {
  const status = getStatus(table);
  const time = formatTime(table.created_at);
  const href =
    table.guests && table.guests.length > 0
      ? `/dashboard/basket/${table.guests[0].client_id}?table=${table.table_number}&tableId=${table.id}`
      : `/dashboard/basket/${table.client_id}?table=${table.table_number}&tableId=${table.id}`;

  // Long-press → context menu (iiko). Fires after a hold with no scroll; the
  // subsequent click is swallowed so the card doesn't also navigate.
  const timer = useRef<number | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const fired = useRef(false);
  const clear = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } };

  const onTouchStart = (e: React.TouchEvent) => {
    if (!onLongPress) return;
    fired.current = false;
    const t = e.touches[0];
    start.current = { x: t.clientX, y: t.clientY };
    timer.current = window.setTimeout(() => {
      fired.current = true;
      try { navigator.vibrate?.(10); } catch { /* ignore */ }
      onLongPress({ x: t.clientX, y: t.clientY });
    }, LONG_PRESS_MS);
  };
  const onTouchMove = (e: React.TouchEvent) => {
    if (!start.current) return;
    const t = e.touches[0];
    if (Math.abs(t.clientX - start.current.x) > MOVE_TOLERANCE || Math.abs(t.clientY - start.current.y) > MOVE_TOLERANCE) clear();
  };
  const onContextMenu = (e: React.MouseEvent) => {
    if (!onLongPress) return;
    e.preventDefault();
    onLongPress({ x: e.clientX, y: e.clientY });
  };
  const onClick = (e: React.MouseEvent) => {
    if (fired.current) { e.preventDefault(); e.stopPropagation(); fired.current = false; }
  };

  const dishes = table.dish_names || [];
  const total = table.dish_count || dishes.length;
  const hasMore = total > 4;
  const shown = hasMore ? dishes.slice(0, 3) : dishes.slice(0, 4);
  const guestCount = table.guests?.length || 0;

  return (
    <Link
      href={href}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={clear}
      onTouchCancel={clear}
      onContextMenu={onContextMenu}
      onClick={onClick}
      className="bg-surface rounded-2xl border border-hair shadow-sm p-3 active:scale-[0.98] transition-transform flex flex-col h-44 select-none [-webkit-touch-callout:none]"
    >
      {/* Title + time (status colour) */}
      <div className="flex items-baseline justify-between gap-2">
        <p className={`font-bold text-sm leading-tight truncate ${status.text}`}>
          {nameOverride ?? `Стол ${table.table_number}`}
        </p>
        <span className={`text-xs font-semibold tabular-nums flex-shrink-0 ${status.text}`}>
          {time}
        </span>
      </div>
      {/* iiko shows the status as coloured text (no dot) under the table number */}
      <p className={`text-xs truncate mt-1 ${status.text}`}>{status.label}</p>

      {/* Dishes */}
      <div className="flex-1 overflow-hidden border-t border-hair-soft mt-2 pt-2">
        {shown.map((d, i) => (
          <p key={i} className="text-xs text-ink truncate leading-[1.4]">
            {d}
          </p>
        ))}
        {hasMore && <p className="text-xs text-ink leading-[1.4]">…</p>}
      </div>

      {/* Footer: guests | price */}
      <div className="border-t border-hair-soft pt-2 mt-2 flex items-center justify-between">
        {guestCount > 0 ? (
          <div className="flex items-center gap-1 text-ink-muted">
            <Users className="h-4 w-4" strokeWidth={2} />
            <span className="text-xs font-medium">{guestCount}</span>
          </div>
        ) : (
          <span />
        )}
        <span className="text-sm font-bold text-ink">
          {table.total_price.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₽
        </span>
      </div>
    </Link>
  );
}

"use client";

import { SwipeRow } from "@/shared/ui/SwipeRow";
import { formatMoney } from "@/shared/lib/utils";
import { useLongPress } from "@/shared/lib/use-long-press";
import { dishStatus } from "../model/dish-status";
import type { BasketItem, ModifierInfo } from "../model/types";

const IconComment = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
);
const IconSplit = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.121 14.121a3 3 0 10-4.243 4.243 3 3 0 004.243-4.243zm0 0L19 4m-9.879 10.121L12 12m0 0l7 7m-7-7L9.121 9.879m0 0a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243z" /></svg>
);
const IconTrash = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
);

export interface DishRowProps {
  item: BasketItem;
  course: string; // "1".."4" | "vip"
  warn: string[]; // matched allergens/dislikes
  onQty: () => void;
  onCourse: () => void;
  onOpen: () => void; // open modifiers
  onComment: () => void;
  onSplit: () => void;
  onRemove: () => void | Promise<void>;
  // Multi-select (iiko long-press) mode
  selecting?: boolean;
  selected?: boolean;
  onLongPress?: () => void; // enter selection mode with this dish picked
  onToggleSelect?: () => void;
}

export function DishRow({ item, course, warn, onQty, onCourse, onOpen, onComment, onSplit, onRemove, selecting = false, selected = false, onLongPress, onToggleSelect }: DishRowProps) {
  const s = dishStatus(item.status); // iiko colour by kitchen status (default = new/blue)
  // A dish already split into halves (qty 0.5 / "(½)" line) can't be split again.
  const isSplit = item.quantity < 1 || item.dish_name.includes("½");
  const lp = useLongPress(onLongPress);

  // ── Selection mode: whole row toggles a checkbox; no swipe, no inner buttons ──
  if (selecting) {
    return (
      <div
        onClick={() => onToggleSelect?.()}
        className={`px-3 py-2 flex items-center gap-3 cursor-pointer select-none [-webkit-touch-callout:none] transition-colors ${selected ? "bg-blue-500/10" : "active:bg-inset"}`}
      >
        <span className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center transition ${selected ? "bg-blue-500" : "border-2 border-hair"}`}>
          {selected && (
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
          )}
        </span>
        <span className={`flex-shrink-0 w-6 text-center text-sm font-semibold ${s.text}`}>{item.quantity}</span>
        <p className={`flex-1 min-w-0 truncate text-sm font-medium ${s.text}`}>{item.dish_name}</p>
        <p className={`flex-shrink-0 text-sm font-semibold ${s.text}`}>{formatMoney(item.subtotal)} ₽</p>
      </div>
    );
  }

  // ── Normal mode: swipe actions + long-press to enter selection ──
  return (
    <div
      className="select-none [-webkit-touch-callout:none]"
      {...lp.handlers}
      onClickCapture={(e) => lp.consumeClick(e)}
    >
    <SwipeRow
      leftActions={[{ label: "Коммент", bg: "bg-blue-500", icon: IconComment, onClick: onComment }]}
      rightActions={[
        ...(isSplit ? [] : [{ label: "Разделить", bg: "bg-orange-500", icon: IconSplit, onClick: onSplit }]),
        { label: "Удалить", bg: "bg-red-500", icon: IconTrash, onClick: () => { void onRemove(); } },
      ]}
    >
      <div className="px-3 py-2">
        <div className="flex items-start gap-3">
          {/* Количество — синяя цифра слева, на одной линии с названием */}
          <button
            onClick={(e) => { e.stopPropagation(); onQty(); }}
            className={`flex-shrink-0 w-7 text-center text-sm font-semibold leading-5 active:opacity-60 ${s.text}`}
          >
            {item.quantity}
          </button>
          {/* Название — цвет по статусу блюда (iiko), тап открывает модификаторы */}
          <div className="flex-1 min-w-0 flex items-start gap-1" onClick={onOpen}>
            <p className={`text-sm font-medium leading-5 cursor-pointer ${s.text}`}>{item.dish_name}</p>
            {warn.length > 0 && (
              <span className="flex-shrink-0 text-xs px-1 leading-5 rounded bg-orange-100 border border-orange-300 text-orange-600 font-semibold" title={`Содержит: ${warn.join(", ")}`}>
                ⚠ {warn.join(", ")}
              </span>
            )}
          </div>
          {/* Цена + Курс. Курс меняется только пока блюдо не отправлено на кухню
              (iiko: у отправленного/готового/поданного курс не выбирается). */}
          <div className="flex-shrink-0 text-right">
            <p className={`text-sm font-semibold leading-5 ${s.text}`}>{formatMoney(item.subtotal)} ₽</p>
            {s.key === "new" ? (
              <button
                onClick={(e) => { e.stopPropagation(); onCourse(); }}
                className="inline-flex items-center gap-1 text-xs text-blue-500 leading-4 mt-1 active:opacity-60"
              >
                {course === "vip" ? "VIP" : `Курс ${course}`}
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" /></svg>
              </button>
            ) : (
              <span className={`inline-block text-xs leading-4 mt-1 ${s.text}`}>
                {s.label}
              </span>
            )}
          </div>
        </div>
        {item.modifiers && item.modifiers.length > 0 && (
          <p className="text-xs text-ink-subtle mt-1 pl-10 truncate">
            {item.modifiers.map((m: ModifierInfo) => `${m.name}${m.amount > 1 ? ` ×${m.amount}` : ""}`).join(", ")}
          </p>
        )}
        {item.comment && <p className="text-xs text-blue-500 mt-1 pl-10 truncate">{item.comment}</p>}
      </div>
    </SwipeRow>
    </div>
  );
}

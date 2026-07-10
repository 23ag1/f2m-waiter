"use client";

import { Sheet } from "@/shared/ui/Sheet";
import { Printer } from "lucide-react";
import { formatMoney } from "@/shared/lib/utils";

// Pre-check (пречек) preview + print action.
export function PrecheckSheet({
  open,
  onClose,
  tableNumber,
  guestCount,
  lines,
  total,
  printing,
  onPrint,
}: {
  open: boolean;
  onClose: () => void;
  tableNumber: string;
  guestCount: number;
  lines: string[];
  total: number;
  printing: boolean;
  onPrint: () => void;
}) {
  return (
    <Sheet open={open} onClose={onClose} title="Пречек">
      <div className="bg-surface rounded-2xl p-4 mb-4">
        <div className="flex items-center justify-between pb-3 border-b border-dashed border-hair">
          <span className="text-base font-bold text-ink">Стол {tableNumber}</span>
          <span className="text-sm text-ink-subtle">Гостей {guestCount}</span>
        </div>
        <div className="py-3 max-h-64 overflow-y-auto divide-y divide-hair-soft">
          {lines.length === 0 ? (
            <p className="text-sm text-ink-subtle text-center py-4">Нет позиций</p>
          ) : (
            lines.map((l, i) => (
              <p key={i} className="text-sm text-ink py-2 leading-snug">{l}</p>
            ))
          )}
        </div>
        <div className="flex items-center justify-between pt-3 border-t border-dashed border-hair">
          <span className="text-sm font-bold text-ink-muted uppercase tracking-wider">Итого</span>
          <span className="text-xl font-bold text-ink">{formatMoney(total)} ₽</span>
        </div>
      </div>
      <button
        onClick={onPrint}
        disabled={printing}
        className="w-full py-4 rounded-2xl bg-black text-white font-bold text-base shadow-md active:scale-[0.98] transition disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {printing ? "Печать..." : (
          <>
            <Printer className="h-5 w-5" />
            Распечатать пречек
          </>
        )}
      </button>
    </Sheet>
  );
}

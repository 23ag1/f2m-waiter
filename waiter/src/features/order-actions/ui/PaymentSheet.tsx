"use client";

import { useState } from "react";
import { Sheet } from "@/shared/ui/Sheet";
import { Button } from "@/shared/ui/button";
import { formatMoney } from "@/shared/lib/utils";

export type PayMethod = "cash" | "card" | "sbp" | "bonus";

const METHODS: { key: PayMethod; label: string; icon: string }[] = [
  { key: "cash", label: "Наличные", icon: "💵" },
  { key: "card", label: "Карта", icon: "💳" },
  { key: "sbp", label: "СБП", icon: "📲" },
  { key: "bonus", label: "Бонусами", icon: "⭐" },
];

// Payment sheet: choose a method (cash shows received/change), then confirm.
export function PaymentSheet({
  open,
  onClose,
  tableNumber,
  total,
  onPaid,
}: {
  open: boolean;
  onClose: () => void;
  tableNumber: string;
  total: number;
  onPaid: (method: PayMethod) => void;
}) {
  const [method, setMethod] = useState<PayMethod | null>(null);
  const [received, setReceived] = useState("");

  const cash = method === "cash";
  const receivedNum = parseFloat(received.replace(",", ".")) || 0;
  const change = Math.max(0, receivedNum - total);
  const canPay = method !== null && (!cash || receivedNum >= total);

  const reset = () => { setMethod(null); setReceived(""); };
  const close = () => { reset(); onClose(); };

  return (
    <Sheet open={open} onClose={close} title={`Оплата · Стол ${tableNumber}`}>
      <div className="bg-surface rounded-2xl p-4 mb-4 flex items-center justify-between">
        <span className="text-sm font-medium text-ink-muted">К оплате</span>
        <span className="text-2xl font-bold text-ink">{formatMoney(total)} ₽</span>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        {METHODS.map((m) => (
          <button
            key={m.key}
            onClick={() => setMethod(m.key)}
            className={`rounded-2xl py-4 flex flex-col items-center gap-1 border-2 transition active:scale-[0.98] ${
              method === m.key ? "border-blue-500 bg-blue-50" : "border-transparent bg-surface"
            }`}
          >
            <span className="text-2xl">{m.icon}</span>
            <span className={`text-sm font-semibold ${method === m.key ? "text-blue-600" : "text-ink"}`}>{m.label}</span>
          </button>
        ))}
      </div>

      {cash && (
        <div className="bg-surface rounded-2xl p-4 mb-4 space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-ink-muted">Получено</span>
            <input
              autoFocus
              inputMode="decimal"
              value={received}
              onChange={(e) => setReceived(e.target.value.replace(/[^0-9.,]/g, ""))}
              placeholder="0"
              className="mt-1 w-full bg-inset rounded-xl px-4 py-3 text-lg font-semibold text-ink outline-none"
            />
          </label>
          <div className="flex items-center justify-between px-1">
            <span className="text-sm font-medium text-ink-muted">Сдача</span>
            <span className="text-lg font-bold text-green-600">{formatMoney(change)} ₽</span>
          </div>
        </div>
      )}

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => { if (canPay && method) { onPaid(method); reset(); } }}
        disabled={!canPay}
        className="shadow-md"
      >
        Оплатить {formatMoney(total)} ₽
      </Button>
    </Sheet>
  );
}

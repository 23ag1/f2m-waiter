"use client";

import { Sheet } from "@/shared/ui/Sheet";
import { Button } from "@/shared/ui/button";
import { Send, Receipt } from "lucide-react";

// "Отправить на печать" sheet: order comment + send + calc(print).
export function SendOrderSheet({
  open,
  onClose,
  comment,
  onComment,
  sending,
  disabled,
  onSend,
  onPrint,
}: {
  open: boolean;
  onClose: () => void;
  comment: string;
  onComment: (v: string) => void;
  sending: boolean;
  disabled: boolean;
  onSend: () => void;
  onPrint: () => void;
}) {
  return (
    <Sheet open={open} onClose={onClose} title="Отправить на печать">
      <div className="relative mb-4">
        <input
          type="text"
          value={comment}
          onChange={(e) => onComment(e.target.value)}
          placeholder="Комментарий к заказу..."
          maxLength={255}
          className="w-full px-4 py-3 bg-inset rounded-2xl text-sm text-ink placeholder-gray-400 focus:outline-none pr-10"
        />
        {comment && (
          <button onClick={() => onComment("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle text-xs">✕</button>
        )}
      </div>
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={onSend}
        disabled={sending || disabled}
        className="gap-2 text-lg mb-2"
      >
        <Send className="h-5 w-5 -ml-1" />
        {sending ? "Отправка..." : "Отправить"}
      </Button>
      <button onClick={onPrint} className="w-full py-3 flex items-center justify-center gap-2 text-blue-500 font-semibold active:opacity-60">
        <Receipt className="h-5 w-5" />
        Расчет
      </button>
    </Sheet>
  );
}

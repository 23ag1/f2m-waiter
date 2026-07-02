"use client";

import { Sheet } from "@/shared/ui/Sheet";

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
      <button
        onClick={onSend}
        disabled={sending || disabled}
        className="w-full py-4 rounded-2xl bg-blue-500 text-white font-bold text-lg flex items-center justify-center gap-2 active:scale-[0.98] transition disabled:opacity-40 mb-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 -ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
        {sending ? "Отправка..." : "Отправить"}
      </button>
      <button onClick={onPrint} className="w-full py-3 flex items-center justify-center gap-2 text-blue-500 font-semibold active:opacity-60">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m-6 4h6m-6 4h4M5 3v18l2-1 2 1 2-1 2 1 2-1 2 1V3l-2 1-2-1-2 1-2-1-2 1-2-1z" /></svg>
        Расчет
      </button>
    </Sheet>
  );
}

"use client";

import { useState, useEffect } from "react";
import { Sheet } from "@/shared/ui/Sheet";

// Order-level comment editor.
export function OrderCommentSheet({
  open,
  onClose,
  initial,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  initial: string;
  onSave: (value: string) => void;
}) {
  const [value, setValue] = useState(initial);
  useEffect(() => { if (open) setValue(initial); }, [open, initial]);

  return (
    <Sheet open={open} onClose={onClose} title="Комментарий к заказу" side="top">
      <textarea
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        maxLength={255}
        rows={3}
        placeholder="Например: гость торопится, подать быстрее"
        className="w-full px-4 py-3 bg-surface border border-hair rounded-2xl text-base text-ink placeholder-gray-400 focus:outline-none focus:border-black transition resize-none"
      />
      <p className="text-xs text-ink-subtle text-right mt-1">{value.length}/255</p>
      <button
        onClick={() => onSave(value.trim())}
        className="w-full mt-3 py-4 rounded-2xl bg-blue-500 text-white font-bold text-base active:scale-[0.98] transition"
      >
        Сохранить
      </button>
    </Sheet>
  );
}

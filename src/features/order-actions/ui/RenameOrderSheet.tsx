"use client";

import { useState, useEffect } from "react";
import { Sheet } from "@/shared/ui/Sheet";

// Rename an order (local display name override).
export function RenameOrderSheet({
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

  const save = () => {
    const v = value.trim();
    if (v) onSave(v);
  };

  return (
    <Sheet open={open} onClose={onClose} title="Переименовать заказ" side="top">
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") save(); }}
        maxLength={40}
        placeholder="Название заказа"
        className="w-full bg-surface border border-hair rounded-2xl px-4 py-4 text-lg font-semibold text-ink outline-none focus:border-black transition"
      />
      <button
        onClick={save}
        disabled={!value.trim()}
        className="w-full mt-3 py-4 rounded-2xl bg-blue-500 text-white font-bold text-base active:scale-[0.98] transition disabled:opacity-40"
      >
        Готово
      </button>
    </Sheet>
  );
}

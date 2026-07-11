"use client";

import { useState, useEffect } from "react";
import { Sheet } from "@/shared/ui/Sheet";
import { Button } from "@/shared/ui/button";

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
    <Sheet open={open} onClose={onClose} title="Комментарий к заказу">
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
      <Button variant="primary" size="lg" fullWidth onClick={() => onSave(value.trim())} className="mt-3">
        Сохранить
      </Button>
    </Sheet>
  );
}

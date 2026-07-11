"use client";

import type { ModifierGroup } from "@/entities/menu";
import { Sheet } from "@/shared/ui/Sheet";
import { Button } from "@/shared/ui/button";
import { Stepper } from "@/shared/ui/Stepper";

// Bottom-sheet modal to pick modifier amounts for a dish.
export function ModifiersModal({
  dishName,
  groups,
  selections,
  onSelect,
  editing,
  onConfirm,
  onClose,
}: {
  dishName: string;
  groups: ModifierGroup[];
  selections: Record<string, number>;
  onSelect: (id: string, amount: number) => void;
  editing: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Sheet open onClose={onClose} scroll>
      <h2 className="text-lg font-bold text-ink mb-1">{dishName}</h2>
      <p className="text-sm text-ink-muted mb-4">Выберите модификаторы</p>
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.group_id}>
            <h3 className="text-sm font-bold text-ink mb-2">
              {group.group_name}
              {group.required && <span className="text-red-500 ml-1">*</span>}
            </h3>
            <div className="space-y-2">
              {group.options.map((opt) => {
                const amount = selections[opt.id] || 0;
                return (
                  <div key={opt.id} className="flex items-center justify-between bg-surface rounded-xl px-3 py-2">
                    <div>
                      <span className="text-sm font-medium text-ink">{opt.name}</span>
                      {opt.price ? <span className="text-xs text-ink-subtle ml-2">+{opt.price} ₽</span> : null}
                    </div>
                    <Stepper
                      size="md"
                      value={amount}
                      onDec={() => onSelect(opt.id, Math.max(opt.min_amount, amount - 1))}
                      onInc={() => onSelect(opt.id, Math.min(opt.max_amount, amount + 1))}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-3 mt-5">
        <Button variant="outline" onClick={onClose} className="flex-1">Отмена</Button>
        <Button variant="dark" onClick={onConfirm} className="flex-1 shadow-md">{editing ? "Сохранить" : "Добавить"}</Button>
      </div>
    </Sheet>
  );
}

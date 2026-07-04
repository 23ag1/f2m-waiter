"use client";

import type { ModifierGroup } from "@/entities/menu";

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
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end justify-center" onClick={onClose}>
      <div className="bg-surface w-full max-w-lg rounded-t-3xl p-5 max-h-[70vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
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
                    <div key={opt.id} className="flex items-center justify-between bg-inset rounded-xl px-3 py-2">
                      <div>
                        <span className="text-sm font-medium text-ink">{opt.name}</span>
                        {opt.price ? <span className="text-xs text-ink-subtle ml-2">+{opt.price} ₽</span> : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => onSelect(opt.id, Math.max(opt.min_amount, amount - 1))} className="w-7 h-7 rounded-lg bg-surface border border-hair flex items-center justify-center text-ink-muted active:scale-95">-</button>
                        <span className="w-5 text-center font-bold text-sm">{amount}</span>
                        <button onClick={() => onSelect(opt.id, Math.min(opt.max_amount, amount + 1))} className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center active:scale-95">+</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-3 mt-5">
          <button onClick={onClose} className="flex-1 py-3 rounded-xl border border-hair text-ink-muted font-semibold hover:bg-inset transition">Отмена</button>
          <button onClick={onConfirm} className="flex-1 py-3 rounded-xl bg-black text-white font-semibold active:scale-[0.98] transition shadow-md">{editing ? "Сохранить" : "Добавить"}</button>
        </div>
      </div>
    </div>
  );
}

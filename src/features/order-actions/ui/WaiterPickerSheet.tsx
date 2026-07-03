"use client";

import { Sheet } from "@/shared/ui/Sheet";
import { Avatar } from "@/shared/ui/Avatar";
import { WAITERS } from "../model/waiters";

// Pick the waiter assigned to an order.
export function WaiterPickerSheet({
  open,
  onClose,
  currentName,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  currentName?: string;
  onPick: (name: string) => void;
}) {
  return (
    <Sheet open={open} onClose={onClose} title="Сменить официанта">
      <div className="bg-surface rounded-2xl overflow-hidden divide-y divide-hair-soft">
        {WAITERS.map((w) => {
          const active = w.name === currentName;
          return (
            <button
              key={w.id}
              onClick={() => onPick(w.name)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left active:bg-inset transition"
            >
              <Avatar initial={w.initial} size="sm" />
              <span className={`flex-1 text-base font-medium ${active ? "text-blue-600" : "text-ink"}`}>{w.name}</span>
              {active && (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </button>
          );
        })}
      </div>
    </Sheet>
  );
}

"use client";

import { formatMoney } from "@/shared/lib/utils";
import type { HungerLevel } from "@/shared/lib/hunger";
import type { GuestData } from "../model/types";
import { HungerDropdown } from "./HungerDropdown";

// Guest header row: name · sum · hunger · allergies/dislikes | + | ⋯
export function GuestRow({
  guest,
  total,
  active = false,
  onSelect,
  onHunger,
  onPlus,
  onMenu,
}: {
  guest: GuestData;
  total: number;
  /** Highlighted (blue) as the guest new dishes go to — shown while the menu is open. */
  active?: boolean;
  onSelect: () => void;
  onHunger: (v: HungerLevel) => void;
  onPlus: () => void;
  onMenu: () => void;
}) {
  return (
    <div onClick={onSelect} className={`flex items-center justify-between gap-2 cursor-pointer transition-all ${active ? "mx-2 my-1 px-3 py-2 rounded-2xl bg-blue-500 shadow-sm" : "px-4 py-2"}`}>
      <div className="flex items-center gap-2 flex-wrap min-w-0">
        <span className={`text-sm font-bold ${active ? "text-white" : "text-ink"}`}>{guest.name}</span>
        <span className={`text-xs ${active ? "text-white/75" : "text-ink-subtle"}`}>· {formatMoney(total)} ₽</span>
        {guest.checkedIn && (
          <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-600 font-semibold">QR</span>
        )}
        <HungerDropdown value={guest.hunger} onChange={onHunger} />
        {guest.allergies?.map((a) => (
          <span key={a} className="text-xs px-2 py-1 rounded bg-red-50 border border-red-200 text-red-500 font-semibold">⚠ {a}</span>
        ))}
        {guest.dislikes?.map((d) => (
          <span key={d} className="text-xs px-2 py-1 rounded bg-orange-50 border border-orange-200 text-orange-500 font-semibold">✕ {d}</span>
        ))}
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={(e) => { e.stopPropagation(); onPlus(); }}
          className={`w-9 h-9 flex items-center justify-center active:scale-90 transition ${active ? "text-white" : "text-blue-500"}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 5v14M5 12h14" /></svg>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onMenu(); }}
          className={`w-9 h-9 flex items-center justify-center active:scale-90 transition ${active ? "text-white/80" : "text-ink-subtle"}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h.01M12 12h.01M19 12h.01" /></svg>
        </button>
      </div>
    </div>
  );
}

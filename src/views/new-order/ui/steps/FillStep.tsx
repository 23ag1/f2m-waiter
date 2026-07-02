"use client";

import { useMemo, useRef, useState } from "react";
import { modifyBasket, removeBasketDish, addGuestToTable, removeGuestFromTable } from "@/shared/api";
import { CATEGORY_COLORS, fetchRealHints, type HintDish } from "@/entities/recommendation";
import { HungerDropdown } from "@/entities/guest";
import type { HungerLevel } from "@/shared/lib/hunger";
import type { BasketItem } from "@/entities/dish";
import type { Dish, Category } from "@/entities/menu";
import type { GuestSlot } from "../../model/types";

function hintColor(category: string) {
  // Pastel cards stay light in both themes (fixed fallback too).
  return CATEGORY_COLORS[category] ?? { border: "border-gray-200", bg: "bg-gray-50", text: "text-gray-500" };
}

interface FillStepProps {
  guestSlots: GuestSlot[];
  setGuestSlots: React.Dispatch<React.SetStateAction<GuestSlot[]>>;
  guestBaskets: Record<number, BasketItem[]>;
  setGuestBaskets: React.Dispatch<React.SetStateAction<Record<number, BasketItem[]>>>;
  guestHints: Record<number, HintDish[]>;
  setGuestHints: React.Dispatch<React.SetStateAction<Record<number, HintDish[]>>>;
  guestDismissed: Record<number, Set<number>>;
  setGuestDismissed: React.Dispatch<React.SetStateAction<Record<number, Set<number>>>>;
  activeGuestIdx: number;
  setActiveGuestIdx: (idx: number) => void;
  menu: Category[];
  menuLoading: boolean;
  isStopped: (dishId: number) => boolean;
  addedIds: Set<number>;
  loadingModifiers: boolean;
  openModifiersOrAdd: (dish: Dish) => void;
  openModifiersForExisting: (clientId: number, item: BasketItem) => void;
  refreshGuest: (clientId: number) => void;
  showToast: (msg: string, type?: "ok" | "err") => void;
  saveWizardState: () => void;
  setGuestHungerNO: (clientId: number, level: HungerLevel) => void;
  openRecs: (clientId: number, name: string) => void;
  sessionTableId: number | null;
  orderComment: string;
  setOrderComment: (v: string) => void;
  sending: boolean;
  onSend: () => void;
  totalDishes: number;
  totalPrice: number;
  setEditingComment: (v: { clientId: number; dishId: number; value: string } | null) => void;
  router: { push: (href: string) => void };
}

// Wizard step 3: per-guest baskets, inline menu, recommendations and send bar.
export function FillStep({
  guestSlots, setGuestSlots, guestBaskets, setGuestBaskets,
  guestHints, setGuestHints, guestDismissed, setGuestDismissed,
  activeGuestIdx, setActiveGuestIdx, menu, menuLoading, isStopped,
  addedIds, loadingModifiers, openModifiersOrAdd, openModifiersForExisting,
  refreshGuest, showToast, saveWizardState, setGuestHungerNO, openRecs,
  sessionTableId, orderComment, setOrderComment, sending, onSend,
  totalDishes, totalPrice, setEditingComment, router,
}: FillStepProps) {
  // Inline-menu + swipe state (local to this step)
  const [menuCollapsed, setMenuCollapsed] = useState(true);
  const [menuSearch, setMenuSearch] = useState("");
  const [activeMenuCategory, setActiveMenuCategory] = useState<string | null>(null);
  const touchRef = useRef<{ x: number; y: number; key: string; locked: boolean } | null>(null);
  const [swipeOffset, setSwipeOffset] = useState<{ key: string; dx: number } | null>(null);

  const filteredMenu = useMemo(() => {
    if (!menuSearch.trim()) return menu;
    const q = menuSearch.toLowerCase();
    return menu
      .map((cat) => ({
        ...cat,
        dishes: cat.dishes.filter(
          (d) => d.name.toLowerCase().includes(q) || (d.description && d.description.toLowerCase().includes(q))
        ),
      }))
      .filter((cat) => cat.dishes.length > 0);
  }, [menu, menuSearch]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">

      {/* Guest list — always visible, takes remaining space, scrolls independently */}
      <div className="flex-1 min-h-0 bg-surface border-b border-hair overflow-y-auto">
        <div className="divide-y divide-hair-soft">
          {guestSlots.map((guest, idx) => {
            const items = guestBaskets[guest.client_id] || [];
            const guestTotal = items.reduce((s, i) => s + Number(i.subtotal), 0);
            const isActive = idx === activeGuestIdx;
            return (
              <div key={guest.client_id}>
                <div
                  onClick={() => setActiveGuestIdx(idx)}
                  className={`flex items-center justify-between cursor-pointer transition px-4 py-3 ${isActive ? "bg-blue-500" : "bg-surface"}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`text-sm font-semibold truncate ${isActive ? "text-white" : "text-ink"}`}>
                      {guest.name}
                    </span>
                    <span className={`text-sm ${isActive ? "text-blue-100" : "text-ink-subtle"}`}>•</span>
                    <span className={`text-sm font-medium ${isActive ? "text-white" : "text-ink-muted"}`}>
                      {guestTotal > 0 ? `${guestTotal} ₽` : "0,00 ₽"}
                    </span>
                    {guest.checkedIn && (
                      <span className={`text-xs px-2 py-1 rounded font-semibold ${isActive ? "bg-surface/20 text-white" : "bg-green-100 text-green-600"}`}>QR</span>
                    )}
                    {guest.allergies?.map((a) => (
                      <span key={a} className={`text-xs px-2 py-1 rounded font-semibold ${isActive ? "bg-surface/20 text-white" : "bg-red-50 border border-red-200 text-red-500"}`}>⚠ {a}</span>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <HungerDropdown value={guest.hunger} onChange={(v) => setGuestHungerNO(guest.client_id, v)} />
                    <button
                      onClick={(e) => { e.stopPropagation(); openRecs(guest.client_id, guest.name); }}
                      className={`w-7 h-7 rounded-lg flex items-center justify-center active:scale-90 transition ${isActive ? "bg-surface/20 text-white" : "bg-blue-50 border border-blue-200 text-blue-500"}`}
                      title="Подсказки"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                    </button>
                    {guestSlots.length > 1 && (
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          if (sessionTableId === null) return;
                          try {
                            await removeGuestFromTable(sessionTableId, guest.client_id);
                            setGuestSlots((prev) => prev.filter((g) => g.client_id !== guest.client_id));
                            setGuestBaskets((prev) => { const n = { ...prev }; delete n[guest.client_id]; return n; });
                            if (activeGuestIdx >= guestSlots.length - 1) setActiveGuestIdx(Math.max(0, guestSlots.length - 2));
                          } catch { showToast("Ошибка удаления гостя", "err"); }
                        }}
                        className={`w-7 h-7 rounded-full flex items-center justify-center transition ${isActive ? "text-white/70 hover:text-white" : "text-ink-subtle hover:text-red-500"}`}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    )}
                  </div>
                </div>
                {items.length > 0 && (
                  <div className="bg-inset/50 divide-y divide-hair-soft">
                    {items.map((item) => {
                      const swKey = `${guest.client_id}-${item.dish_id}`;
                      const dx = swipeOffset?.key === swKey ? swipeOffset.dx : 0;
                      return (
                      <div key={item.dish_id} className="relative overflow-hidden">
                        {/* Swipe backgrounds */}
                        {dx > 0 && <div className="absolute inset-0 bg-blue-500 flex items-center pl-4"><span className="text-white text-xs font-bold">Коммент.</span></div>}
                        {dx < 0 && <div className="absolute inset-0 bg-red-500 flex items-center justify-end pr-4"><span className="text-white text-xs font-bold">Удалить</span></div>}
                        <div
                          className="px-4 pl-12 py-2 bg-surface relative z-[1] transition-transform"
                          style={{ transform: `translateX(${dx}px)` }}
                          onTouchStart={(e) => { touchRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY, key: swKey, locked: false }; }}
                          onTouchMove={(e) => {
                            if (!touchRef.current || touchRef.current.key !== swKey) return;
                            const tdx = e.touches[0].clientX - touchRef.current.x;
                            const tdy = e.touches[0].clientY - touchRef.current.y;
                            if (!touchRef.current.locked && Math.abs(tdy) > Math.abs(tdx)) { touchRef.current = null; return; }
                            touchRef.current.locked = true;
                            setSwipeOffset({ key: swKey, dx: Math.max(-100, Math.min(100, tdx)) });
                          }}
                          onTouchEnd={async () => {
                            if (dx > 60) {
                              setEditingComment({ clientId: guest.client_id, dishId: item.dish_id, value: item.comment || "" });
                            } else if (dx < -60) {
                              await removeBasketDish(guest.client_id, item.dish_id);
                              refreshGuest(guest.client_id);
                            }
                            setSwipeOffset(null);
                            touchRef.current = null;
                          }}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex-1 min-w-0 flex items-center gap-1">
                              <p className="text-xs text-ink truncate cursor-pointer active:text-ink" onClick={() => openModifiersForExisting(guest.client_id, item)}>{item.dish_name}</p>
                              <button
                                onClick={() => setEditingComment({ clientId: guest.client_id, dishId: item.dish_id, value: item.comment || "" })}
                                className={`flex-shrink-0 w-5 h-5 rounded flex items-center justify-center text-xs ${item.comment ? "text-blue-500" : "text-ink-subtle"}`}
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" /></svg>
                              </button>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <button
                                onClick={async () => {
                                  if (item.quantity <= 1) {
                                    await removeBasketDish(guest.client_id, item.dish_id);
                                  } else {
                                    await modifyBasket(guest.client_id, item.dish_id, -1);
                                  }
                                  refreshGuest(guest.client_id);
                                }}
                                className="w-6 h-6 rounded-md bg-inset text-ink-muted flex items-center justify-center text-xs font-bold active:scale-95"
                              >-</button>
                              <span className="text-xs font-bold text-ink w-4 text-center">{item.quantity}</span>
                              <button
                                onClick={async () => {
                                  await modifyBasket(guest.client_id, item.dish_id, 1);
                                  refreshGuest(guest.client_id);
                                }}
                                className="w-6 h-6 rounded-md bg-blue-500 text-white flex items-center justify-center text-xs font-bold active:scale-95"
                              >+</button>
                            </div>
                          </div>
                          {item.modifiers && item.modifiers.length > 0 && (
                            <p className="text-xs text-ink-subtle mt-1 truncate">
                              {item.modifiers.map((m) => `${m.name}${m.amount > 1 ? ` ×${m.amount}` : ""}`).join(", ")}
                            </p>
                          )}
                          {item.comment && <p className="text-xs text-blue-500 mt-1 truncate">{item.comment}</p>}
                        </div>
                      </div>
                      );
                    })}
                  </div>
                )}
                {/* Inline hint strip */}
                {(() => {
                  const dismissed = guestDismissed[guest.client_id] ?? new Set<number>();
                  const gHints = (guestHints[guest.client_id] ?? []).filter(h => !dismissed.has(h.id));
                  if (gHints.length === 0) return null;
                  return (
                    <div className="overflow-x-auto px-4 py-2 bg-blue-50/40 border-t border-blue-100">
                      <div className="flex gap-2 w-max">
                        {gHints.map((hint) => {
                          const c = hintColor(hint.category);
                          return (
                            <div key={hint.id} className={`flex-shrink-0 w-28 ${c.bg} border ${c.border} rounded-lg px-2 py-2 flex flex-col gap-1`}>
                              <div className="flex items-start justify-between gap-1">
                                <p className="text-xs font-semibold text-gray-800 leading-tight line-clamp-2 flex-1">{hint.name}</p>
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await modifyBasket(guest.client_id, hint.id, 1);
                                    refreshGuest(guest.client_id);
                                  }}
                                  className="flex-shrink-0 w-4 h-4 rounded bg-blue-500 text-white flex items-center justify-center text-xs font-bold active:scale-90"
                                >+</button>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className={`text-xs font-semibold ${c.text}`}>{hint.category}</span>
                                <span className="text-xs text-gray-500">{hint.price} ₽</span>
                              </div>
                              {hint.tags.length > 0 && (
                                <div className="flex gap-1 overflow-hidden">
                                  {hint.tags.map((tag) => (
                                    <span key={tag} className="flex-shrink-0 text-xs px-1 py-px rounded-full bg-blue-50 text-blue-600 border border-blue-100 font-medium whitespace-nowrap">{tag}</span>
                                  ))}
                                </div>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setGuestDismissed((prev) => ({ ...prev, [guest.client_id]: new Set([...(prev[guest.client_id] ?? []), hint.id]) }));
                                }}
                                className="text-xs text-gray-400 hover:text-gray-600 text-left transition"
                              >не сейчас</button>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}
              </div>
            );
          })}
        </div>
        <div className="flex justify-center py-4 border-t border-hair-soft">
          <button
            onClick={async () => {
              if (sessionTableId === null) return;
              try {
                const res = await addGuestToTable(sessionTableId);
                const newIdx = guestSlots.length;
                const newSlot: GuestSlot = {
                  guest_id: res.guest.slot_index ?? newIdx,
                  client_id: res.guest.client_id,
                  name: res.guest.name,
                  slot_index: newIdx,
                  linked: false,
                  dish_count: 0,
                };
                setGuestSlots((prev) => [...prev, newSlot]);
                setGuestBaskets((prev) => ({ ...prev, [newSlot.client_id]: [] }));
                setActiveGuestIdx(newIdx);
                // Load hints immediately without waiting for basket (it's empty for new guest)
                fetchRealHints(newSlot.client_id, {})
                  .then(hints => setGuestHints((ph) => ({ ...ph, [newSlot.client_id]: hints })));
              } catch (e) {
                console.error(e);
                showToast("Ошибка добавления гостя", "err");
              }
            }}
            className="px-6 py-2.5 rounded-full bg-surface border border-hair shadow-sm text-sm font-bold text-blue-500 active:scale-95 transition"
          >
            + Гость
          </button>
        </div>
      </div>

      {/* Menu section — in-flow, shrinks guest list as it grows */}
      <div className="shrink-0 bg-surface border-t-2 border-hair shadow-[0_-2px_8px_rgba(0,0,0,0.06)]">
        {/* Gray handle — always visible, acts as toggle */}
        <button
          onClick={() => setMenuCollapsed(!menuCollapsed)}
          className="w-full flex flex-col items-center py-1 active:bg-inset transition"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-6 text-ink-subtle transition-transform ${menuCollapsed ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Menu content — only when open */}
        {!menuCollapsed && (
          <div className="overflow-y-auto max-h-[60vh]">
            {/* Search bar with QR button */}
            <div className="px-3 pb-2 border-b border-hair-soft">
              <div className="relative flex gap-2">
                <div className="relative flex-1">
                  <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-subtle" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    value={menuSearch}
                    onChange={(e) => setMenuSearch(e.target.value)}
                    placeholder="Поиск позиций"
                    className="w-full pl-9 pr-3 py-3 bg-inset border border-hair rounded-xl text-sm text-ink placeholder-gray-400 focus:outline-none focus:border-black transition"
                  />
                  {menuSearch && (
                    <button onClick={() => setMenuSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle hover:text-ink text-sm">
                      ✕
                    </button>
                  )}
                </div>
                {/* QR scan button */}
                <button
                  onClick={() => {
                    saveWizardState();
                    router.push(`/dashboard/scan?returnTo=/dashboard/new-order&guestIdx=${activeGuestIdx}`);
                  }}
                  className="flex-shrink-0 w-11 h-11 rounded-xl bg-inset border border-hair flex items-center justify-center text-ink-muted active:scale-95 transition"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm14 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Menu content */}
            <div className="p-3 pb-4">
              {menuLoading ? (
                <div className="text-center py-8 text-ink-subtle text-sm">Загрузка меню...</div>
              ) : filteredMenu.length === 0 ? (
                <div className="text-center py-8 text-ink-subtle text-sm">
                  {menuSearch ? "Ничего не найдено" : "Меню пусто"}
                </div>
              ) : !menuSearch && !activeMenuCategory ? (
                /* Category grid — iiko-style colored tiles by meaning */
                <div className="grid grid-cols-3 gap-2">
                  {filteredMenu.map((cat, i) => {
                    const n = cat.category_name.toLowerCase();
                    let palette = "";
                    if (n.includes("горяч") || n.includes("мяс") || n.includes("стейк") || n.includes("мангал") || n.includes("птиц") || n.includes("корейск"))
                      palette = "bg-red-100 text-red-800";
                    else if (n.includes("суп") || n.includes("бульон"))
                      palette = "bg-sky-100 text-sky-800";
                    else if (n.includes("салат"))
                      palette = "bg-emerald-100 text-emerald-800";
                    else if (n.includes("десерт") || n.includes("торт") || n.includes("шоколад") || n.includes("сладк") || n.includes("вафл"))
                      palette = "bg-purple-100 text-purple-800";
                    else if (n.includes("закуск") || n.includes("тарелк") || n.includes("брускетт"))
                      palette = "bg-amber-100 text-amber-800";
                    else if (n.includes("паст") || n.includes("пицц") || n.includes("лапш"))
                      palette = "bg-yellow-100 text-yellow-800";
                    else if (n.includes("рыб") || n.includes("морепродукт") || n.includes("лосос"))
                      palette = "bg-teal-100 text-teal-800";
                    else if (n.includes("безалкогол") || n.includes("лимонад") || n.includes("смузи") || n.includes("сок"))
                      palette = "bg-cyan-100 text-cyan-800";
                    else if (n.includes("чай") || n.includes("кофе") || n.includes("капуч") || n.includes("горячий напит"))
                      palette = "bg-stone-100 text-stone-700";
                    else if (n.includes("вин") || n.includes("шампанск") || n.includes("просекк"))
                      palette = "bg-rose-100 text-rose-800";
                    else if (n.includes("пиво") || n.includes("пив") || n.includes("бут."))
                      palette = "bg-orange-100 text-orange-800";
                    else if (n.includes("алкогол") || n.includes("коктейл") || n.includes("лонги") || n.includes("крепк"))
                      palette = "bg-indigo-100 text-indigo-800";
                    else if (n.includes("детск"))
                      palette = "bg-pink-100 text-pink-800";
                    else if (n.includes("напит") || n.includes("бар"))
                      palette = "bg-blue-100 text-blue-800";
                    else {
                      const fallbacks = ["bg-slate-100 text-slate-700","bg-lime-100 text-lime-800","bg-violet-100 text-violet-800","bg-fuchsia-100 text-fuchsia-800"];
                      palette = fallbacks[i % fallbacks.length];
                    }
                    return (
                      <button
                        key={i}
                        onClick={() => setActiveMenuCategory(cat.category_name)}
                        className={`${palette} rounded-xl px-2 py-3 text-left transition active:scale-[0.97] min-h-[64px] flex flex-col justify-between`}
                      >
                        <h3 className="font-semibold text-xs leading-tight">{cat.category_name}</h3>
                        <p className="text-xs opacity-60 mt-1">{cat.dishes.length} поз.</p>
                      </button>
                    );
                  })}
                </div>
              ) : (
                /* Dish list */
                <>
                  {activeMenuCategory && !menuSearch && (
                    <button
                      onClick={() => setActiveMenuCategory(null)}
                      className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink transition mb-2"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                      </svg>
                      Все категории
                    </button>
                  )}
                  {(activeMenuCategory ? filteredMenu.filter(c => c.category_name === activeMenuCategory) : filteredMenu).map((cat, i) => (
                    <div key={i} className="mb-4">
                      <h2 className="text-sm font-bold text-ink mb-2 px-1">{cat.category_name}</h2>
                      <div className="space-y-2">
                        {cat.dishes.map((dish) => {
                          const stopped = isStopped(dish.id);
                          return (
                            <div
                              key={dish.id}
                              className={`bg-surface px-3 py-3 rounded-xl border border-hair-soft flex items-center gap-3 transition ${
                                stopped ? "opacity-40" : "active:scale-[0.98]"
                              }`}
                            >
                              <div className="flex-1 min-w-0">
                                <p className={`text-sm font-medium truncate ${stopped ? "text-ink-subtle line-through" : "text-ink"}`}>{dish.name}</p>
                                <p className={`text-xs ${stopped ? "text-ink-subtle" : "text-ink-muted"}`}>{dish.price} ₽</p>
                              </div>
                              {!stopped ? (
                                <button
                                  onClick={() => openModifiersOrAdd(dish)}
                                  disabled={loadingModifiers}
                                  className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm transition shadow-sm ${
                                    addedIds.has(dish.id) ? "bg-green-500 text-white" : "bg-blue-500 text-white active:scale-90"
                                  }`}
                                >
                                  {addedIds.has(dish.id) ? "✓" : "+"}
                                </button>
                              ) : (
                                <span className="text-xs font-bold text-red-500 bg-red-50 px-2 py-1 rounded-lg">СТОП</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom bar: Order comment + Send — in-flow, not fixed */}
      <div className="shrink-0 bg-surface border-t border-hair p-3 pb-8 shadow-[0_-4px_20px_rgba(0,0,0,0.05)]">
        <div className="max-w-lg mx-auto space-y-2">
          <div className="relative">
            <input
              type="text"
              value={orderComment}
              onChange={(e) => setOrderComment(e.target.value)}
              placeholder="Комментарий к заказу..."
              maxLength={255}
              className="w-full px-3 py-3 bg-inset border border-hair rounded-xl text-sm text-ink placeholder-gray-400 focus:outline-none focus:border-black transition pr-10"
            />
            {orderComment && (
              <button onClick={() => setOrderComment("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle hover:text-ink text-xs">✕</button>
            )}
          </div>
          <button
            onClick={onSend}
            disabled={sending || totalDishes === 0}
            className="w-full bg-blue-500 text-white rounded-xl py-4 font-semibold shadow-md active:bg-blue-600 transition active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {sending ? "Отправка..." : (
              <>
                <span>Отправить в iiko</span>
                {totalDishes > 0 && (
                  <span className="bg-surface/20 px-2 py-1 rounded-lg text-xs">{totalDishes} бл. / {totalPrice} ₽</span>
                )}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

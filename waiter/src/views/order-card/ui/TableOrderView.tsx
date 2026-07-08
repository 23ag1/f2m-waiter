"use client";

import { useState, useMemo } from "react";
import { Toast } from "@/shared/ui/Toast";
import { useToast } from "@/shared/lib/use-toast";
import { Sheet, ActionSheet } from "@/shared/ui/Sheet";
import { BackButton } from "@/shared/ui/BackButton";
import { IconButton } from "@/shared/ui/IconButton";
import { DishRow } from "@/entities/dish";
import { MenuPanel } from "@/widgets/menu-panel";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { modifyBasket, removeBasketDish, splitDish, sendDishes } from "@/shared/api";
import { DISH_INGREDIENTS, HintStrip } from "@/entities/recommendation";
import { QRScannerModal } from "@/shared/ui/QRScannerModal";
import { GuestRow, type GuestData } from "@/entities/guest";
import { useSendOrder, SendOrderSheet } from "@/features/send-order";
import { useAddDish, ModifiersModal } from "@/features/add-dish";
import { useTableSession } from "../model/use-table-session";
import { useMenu } from "@/entities/menu";

// Multi-guest table order (iiko-style): guest list + inline menu + recommendations.
export function TableOrderView() {
  const router = useRouter();
  const { clientId } = useParams();
  const searchParams = useSearchParams();
  const tableIdParam = searchParams.get("tableId");
  const tableParam = searchParams.get("table") || "";

  const { toast, showToast } = useToast();

  const [loading, setLoading] = useState(true);

  // Table session (guests + baskets + per-guest recommendations) — view model
  const {
    guests, guestBaskets, guestHints,
    activeGuestIdx, setActiveGuestIdx,
    refreshGuest, setGuestHunger, addHintDishLocally, replaceHint, checkin, addGuest, removeGuest, renameGuest: applyRename,
  } = useTableSession(tableIdParam, { setLoading, showToast });
  const [showQRScanner, setShowQRScanner] = useState(false);

  // Inline menu — data loaded by useMenu hook
  const { menu, loading: menuLoading, stoppedIds } = useMenu(!!tableIdParam);
  const [menuSearch, setMenuSearch] = useState("");
  const [activeMenuCategory, setActiveMenuCategory] = useState<string | null>(null);
  // Add dish (modifiers flow) — feature
  const addDish = useAddDish({
    getTargetClientId: () => guests[activeGuestIdx]?.client_id,
    refreshGuest,
    stoppedIds,
    showToast,
  });

  // Send order / print (feature)
  const { sending, send, print } = useSendOrder({
    tableId: tableIdParam,
    clientId: Number(clientId),
    tableNum: tableParam,
    showToast,
    onDone: () => router.push("/dashboard"),
  });

  // Comments
  const [orderComment, setOrderComment] = useState("");
  const [editingComment, setEditingComment] = useState<{ clientId: number; dishId: number; value: string } | null>(null);

  // Menu panel toggle
  const [menuCollapsed, setMenuCollapsed] = useState(true);
  // Guest-row ⋯ action sheet + rename modal
  const [guestMenuFor, setGuestMenuFor] = useState<number | null>(null);
  const [renameGuest, setRenameGuest] = useState<{ clientId: number; value: string } | null>(null);
  // Dish quantity popup (enter number) + course picker (local only — backend has no course field)
  const [qtyEdit, setQtyEdit] = useState<{ clientId: number; dishId: number; current: number; value: string } | null>(null);
  const [courseFor, setCourseFor] = useState<{ clientId: number; dishId: number } | null>(null);
  // Split picker: the dish held by `sourceCid` is split among the checked guests.
  const [splitFor, setSplitFor] = useState<{ sourceCid: number; dishId: number; name: string } | null>(null);
  const [splitTargets, setSplitTargets] = useState<Set<number>>(new Set());
  // Multi-select (iiko long-press) mode. Keys are `${clientId}:${dishId}`.
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const selKey = (cid: number, dishId: number) => `${cid}:${dishId}`;
  const enterSelect = (cid: number, dishId: number) => { setSelecting(true); setSelected(new Set([selKey(cid, dishId)])); };
  const toggleSelect = (cid: number, dishId: number) => setSelected((prev) => {
    const n = new Set(prev); const k = selKey(cid, dishId); n.has(k) ? n.delete(k) : n.add(k); return n;
  });
  const exitSelect = () => { setSelecting(false); setSelected(new Set()); };
  const selectedList = () => [...selected].map((k) => { const [c, d] = k.split(":"); return { cid: Number(c), dishId: Number(d) }; });
  const [courses, setCourses] = useState<Record<string, string>>({});
  // Header ⋯ menu + order type + sort-by-course (order type / discounts have no backend yet)
  const [headerMenu, setHeaderMenu] = useState(false);
  const [orderTypeSheet, setOrderTypeSheet] = useState(false);
  const [orderType, setOrderType] = useState<string>("hall");
  const [sortByCourse, setSortByCourse] = useState(false);
  const [sendSheet, setSendSheet] = useState(false); // "Отправить на печать" sheet

  // Swipe state

  const guestRestrictions = (g: GuestData): string[] => [
    ...(g.allergies ?? []),
    ...(g.dislikes ?? []),
  ];

  // ── Selection-mode bulk actions ──
  const deleteSelected = async () => {
    const items = selectedList();
    exitSelect();
    const cids = new Set<number>();
    for (const { cid, dishId } of items) { try { await removeBasketDish(cid, dishId); cids.add(cid); } catch { /* ignore */ } }
    cids.forEach((c) => refreshGuest(c));
    showToast("Удалено");
  };

  // Send ONLY the selected dishes to the kitchen (iiko), not the whole order.
  const sendSelected = async () => {
    if (!tableIdParam) return;
    const items = selectedList();
    if (items.length === 0) return;
    const dishIds = [...new Set(items.map((i) => i.dishId))];
    try {
      const res = await sendDishes(Number(tableIdParam), dishIds);
      exitSelect();
      items.forEach(({ cid }) => refreshGuest(cid));
      showToast(res?.message || "Отправлено на кухню");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Не удалось отправить", "err");
    }
  };


  // ONE split entry point — used by the dish swipe, the long-press toolbar and
  // the row action. Only the trigger differs; the action is identical.
  const openSplit = (cid: number, dishId: number) => {
    const it = (guestBaskets[cid] ?? []).find((i) => i.dish_id === dishId);
    if (!it || it.quantity < 1 || it.dish_name.includes("½")) { showToast("Это блюдо нельзя разделить", "err"); return; }
    if (guests.length < 2) { showToast("Нужно минимум 2 гостя для разделения", "err"); return; }
    exitSelect();
    setSplitFor({ sourceCid: cid, dishId, name: it.dish_name });
    setSplitTargets(new Set([cid])); // the dish owner always shares in the split
  };

  const splitSelected = () => {
    const items = selectedList();
    if (items.length !== 1) { showToast("Разделить можно одно блюдо", "err"); return; }
    openSplit(items[0].cid, items[0].dishId);
  };

  // Split a whole dish into halves shared between the checked guests (iiko: each
  // gets amount 0.5, tagged with their guestId). Backend supports exactly 2.
  const doSplit = async () => {
    if (!splitFor || !tableIdParam) return;
    const targets = [...splitTargets];
    const { sourceCid, dishId } = splitFor;
    setSplitFor(null);
    try {
      await splitDish(Number(tableIdParam), sourceCid, dishId, targets);
      [...new Set([sourceCid, ...targets])].forEach((c) => refreshGuest(c));
      showToast("Блюдо разделено", "ok");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Не удалось разделить", "err");
    }
  };

  // Filtered menu
  const filteredMenu = useMemo(() => {
    if (!menuSearch.trim()) return menu;
    const q = menuSearch.toLowerCase();
    return menu
      .map((cat) => ({
        ...cat,
        dishes: cat.dishes.filter(
          (d) =>
            d.name.toLowerCase().includes(q) ||
            (d.description && d.description.toLowerCase().includes(q))
        ),
      }))
      .filter((cat) => cat.dishes.length > 0);
  }, [menu, menuSearch]);

  // Totals
  const totalDishes = Object.values(guestBaskets).reduce(
    (sum, items) => sum + items.reduce((s, i) => s + i.quantity, 0),
    0
  );

  const isStopped = (dishId: number) => stoppedIds.has(dishId);

  if (loading) {
    return <div className="min-h-screen bg-app flex items-center justify-center text-ink-subtle">Загрузка...</div>;
  }

  if (guests.length === 0) {
    return (
      <div className="min-h-screen bg-app flex flex-col items-center justify-center gap-4 text-ink-subtle">
        <p>Нет гостей за этим столом</p>
        <button onClick={() => router.push("/dashboard")} className="text-blue-500 font-medium">На главную</button>
      </div>
    );
  }

  return (
      <div className="h-screen bg-app flex flex-col overflow-hidden">
        {/* Header — selection mode shows count + Готово; otherwise the iiko header */}
        {selecting ? (
          <header className="shrink-0 bg-inset px-4 pt-3 pb-2 flex items-center justify-between gap-3 z-10">
            <span className="w-16" />
            <h1 className="text-lg font-bold text-ink">{selected.size}</h1>
            <button onClick={exitSelect} className="w-16 text-right text-blue-500 font-bold text-base active:opacity-60">Готово</button>
          </header>
        ) : (
        <header className="shrink-0 bg-inset px-3 pt-2 pb-2 flex items-center gap-3 z-10">
          <BackButton onClick={() => router.push("/dashboard")} />
          <div className="flex-1 min-w-0 text-center">
            <h1 className="text-lg font-bold text-ink leading-tight truncate">Стол {tableParam}</h1>
            <p className="text-xs text-ink-muted">Гостей {guests.length}</p>
          </div>
          {/* Right pill: глаз + скан/QR + ⋯ (iiko) */}
          <div className="flex items-center bg-surface rounded-full shadow-sm px-1 flex-shrink-0">
            <IconButton ariaLabel="Предпросмотр" onClick={() => showToast("Предпросмотр — скоро")}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </IconButton>
            <IconButton ariaLabel="Сканировать" onClick={() => setShowQRScanner(true)}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm14 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
              </svg>
            </IconButton>
            <IconButton ariaLabel="Меню заказа" onClick={() => setHeaderMenu(true)}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h.01M12 12h.01M19 12h.01" />
              </svg>
            </IconButton>
          </div>
        </header>
        )}

        {/* Guest list — always visible, takes remaining space, scrolls independently */}
        <div className="flex-1 min-h-0 bg-surface border-b border-hair overflow-y-auto">
          <div className="divide-y divide-hair-soft">
            {guests.map((guest, idx) => {
              const rawItems = guestBaskets[guest.client_id] || [];
              const items = sortByCourse
                ? [...rawItems].sort((a, b) => {
                    const rank = (id: number) => { const c = courses[`${guest.client_id}-${id}`]; return c === "vip" ? 5 : c ? parseInt(c, 10) : 6; };
                    return rank(a.dish_id) - rank(b.dish_id);
                  })
                : rawItems;
              const guestTotal = items.reduce((s, i) => s + Number(i.subtotal), 0);
              return (
                <div key={guest.client_id}>
                  <GuestRow
                    guest={guest}
                    total={guestTotal}
                    active={!menuCollapsed && idx === activeGuestIdx}
                    onSelect={() => setActiveGuestIdx(idx)}
                    onHunger={(v) => setGuestHunger(guest.client_id, v)}
                    onPlus={() => { setActiveGuestIdx(idx); setMenuCollapsed(false); }}
                    onMenu={() => setGuestMenuFor(guest.client_id)}
                  />
                  {items.length > 0 && (
                    <div className="divide-y divide-hair-soft">
                      {items.map((item) => {
                        const restrictions = guestRestrictions(guest);
                        const ings = DISH_INGREDIENTS[item.dish_id] ?? [];
                        const warn = restrictions.filter((r) =>
                          ings.some((ing) => ing.toLowerCase().includes(r.toLowerCase()) || r.toLowerCase().includes(ing.toLowerCase()))
                        );
                        return (
                          <DishRow
                            key={item.dish_id}
                            item={item}
                            course={courses[`${guest.client_id}-${item.dish_id}`] || "1"}
                            warn={warn}
                            onQty={() => setQtyEdit({ clientId: guest.client_id, dishId: item.dish_id, current: item.quantity, value: String(item.quantity) })}
                            onCourse={() => setCourseFor({ clientId: guest.client_id, dishId: item.dish_id })}
                            onOpen={() => addDish.openForExisting(guest.client_id, item)}
                            onComment={() => setEditingComment({ clientId: guest.client_id, dishId: item.dish_id, value: item.comment || "" })}
                            onSplit={() => openSplit(guest.client_id, item.dish_id)}
                            onRemove={async () => { await removeBasketDish(guest.client_id, item.dish_id); refreshGuest(guest.client_id); }}
                            selecting={selecting}
                            selected={selected.has(selKey(guest.client_id, item.dish_id))}
                            onLongPress={() => enterSelect(guest.client_id, item.dish_id)}
                            onToggleSelect={() => toggleSelect(guest.client_id, item.dish_id)}
                          />
                        );
                      })}
                    </div>
                  )}
                  {/* Collapsible hint strip per guest (рекомендации) */}
                  <HintStrip
                    hints={guestHints[guest.client_id] ?? []}
                    onAdd={(hint) => addHintDishLocally(guest.client_id, hint)}
                    onReplace={(hint, dir) => replaceHint(guest.client_id, hint, dir)}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-center py-4 border-t border-dashed border-hair">
            <button
              onClick={addGuest}
              className="px-6 py-2 rounded-full bg-surface border border-hair shadow-sm text-sm font-bold text-blue-500 active:scale-95 transition"
            >
              + Гость
            </button>
          </div>
        </div>

        {/* Inline menu (widget) */}
        <MenuPanel
          collapsed={menuCollapsed}
          onToggle={() => setMenuCollapsed(!menuCollapsed)}
          loading={menuLoading}
          categories={filteredMenu}
          search={menuSearch}
          activeCategory={activeMenuCategory}
          onCategory={setActiveMenuCategory}
          isStopped={isStopped}
          onAdd={addDish.openForDish}
          adding={addDish.loading}
          addedIds={addDish.addedIds}
        />

        {/* Bottom action bar in selection mode (iiko): delete · split · send-to-kitchen */}
        {selecting ? (
          <div className="shrink-0 bg-surface border-t border-hair px-4 pt-3 pb-8 shadow-[0_-4px_20px_rgba(0,0,0,0.06)] flex items-center justify-around">
            {/* Удалить */}
            <button onClick={deleteSelected} disabled={selected.size === 0} className="w-11 h-11 rounded-full bg-inset flex items-center justify-center text-ink active:scale-90 transition disabled:opacity-30">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
            {/* Перенести в новый заказ (нужен бэкенд переноса между заказами) */}
            <button onClick={() => { if (selected.size === 0) return; showToast("Перенос в новый заказ — скоро"); }} disabled={selected.size === 0} className="w-11 h-11 rounded-full bg-inset flex items-center justify-center text-ink active:scale-90 transition disabled:opacity-30">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
            </button>
            {/* Разделить — только 1 блюдо и 2+ гостя */}
            <button onClick={splitSelected} disabled={selected.size !== 1 || guests.length < 2} className="w-11 h-11 rounded-full bg-inset flex items-center justify-center text-ink active:scale-90 transition disabled:opacity-30">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.121 14.121a3 3 0 10-4.243 4.243 3 3 0 004.243-4.243zm0 0L19 4m-9.879 10.121L12 12m0 0l7 7m-7-7L9.121 9.879m0 0a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243z" /></svg>
            </button>
            {/* Перенести в другой заказ / стол (нужен бэкенд перемещения между столами) */}
            <button onClick={() => { if (selected.size === 0) return; showToast("Перенос в другой заказ — скоро"); }} disabled={selected.size === 0} className="w-11 h-11 rounded-full bg-inset flex items-center justify-center text-ink active:scale-90 transition disabled:opacity-30">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4M16 17H4m0 0l4 4m-4-4l4-4" /></svg>
            </button>
            {/* Отправить на кухню — ключевая: только выбранные блюда */}
            <button onClick={sendSelected} disabled={selected.size === 0} className="w-11 h-11 rounded-full bg-blue-500 flex items-center justify-center text-white shadow-md active:scale-90 transition disabled:opacity-30">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 -ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
            </button>
          </div>
        ) : (
        /* Bottom bar — search + send (iiko) */
        <div className="shrink-0 bg-surface border-t border-hair px-3 pt-2 pb-8 shadow-[0_-4px_20px_rgba(0,0,0,0.05)]">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-subtle" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={menuSearch}
                onChange={(e) => { setMenuSearch(e.target.value); setMenuCollapsed(false); }}
                onFocus={() => setMenuCollapsed(false)}
                placeholder="Поиск позиций"
                className="w-full pl-9 pr-11 py-3 bg-inset rounded-full text-sm text-ink placeholder-gray-500 focus:outline-none"
              />
              <button onClick={() => setShowQRScanner(true)} className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-ink-muted active:scale-90 transition">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7V4h3M20 7V4h-3M4 17v3h3M20 17v3h-3M4 12h16" />
                </svg>
              </button>
            </div>
            <button
              onClick={() => setSendSheet(true)}
              disabled={totalDishes === 0}
              className="flex-shrink-0 w-12 h-12 rounded-full bg-blue-500 text-white flex items-center justify-center shadow-md active:scale-95 transition disabled:opacity-40"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 -ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
        </div>
        )}

        {/* Отправить на печать (feature) */}
        <SendOrderSheet
          open={sendSheet}
          onClose={() => setSendSheet(false)}
          comment={orderComment}
          onComment={setOrderComment}
          sending={sending}
          disabled={totalDishes === 0}
          onSend={() => { setSendSheet(false); send(orderComment); }}
          onPrint={() => { setSendSheet(false); print(); }}
        />

        {/* Разделить блюдо — отметить галочками, между кем делим (мин. 2, бэк = 2) */}
        <Sheet open={!!splitFor} onClose={() => setSplitFor(null)} title={splitFor ? `Разделить «${splitFor.name}»` : "Разделить"}>
          <p className="text-xs text-ink-muted mb-3">Между кем разделить (по ½ каждому):</p>
          <div className="space-y-2 mb-4 max-h-[40vh] overflow-y-auto">
            {guests.map((g, i) => {
              const on = splitTargets.has(g.client_id);
              const isOwner = splitFor?.sourceCid === g.client_id;
              return (
                <button
                  key={g.client_id}
                  onClick={() => setSplitTargets((prev) => { const n = new Set(prev); n.has(g.client_id) ? n.delete(g.client_id) : n.add(g.client_id); return n; })}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl border transition ${on ? "bg-blue-500/10 border-blue-500" : "bg-inset border-hair"}`}
                >
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${on ? "bg-blue-500" : "border-2 border-hair"}`}>
                    {on && <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                  </span>
                  <span className="flex-1 text-left text-sm font-semibold text-ink">{g.name?.trim() || `Гость ${i + 1}`}{isOwner && <span className="text-ink-subtle font-normal"> · владелец</span>}</span>
                </button>
              );
            })}
          </div>
          <button
            onClick={doSplit}
            disabled={splitTargets.size !== 2}
            className="w-full py-4 rounded-2xl bg-blue-500 text-white font-bold text-base active:scale-[0.98] transition disabled:opacity-40"
          >
            {splitTargets.size === 2 ? "Разделить" : "Отметьте 2 гостей"}
          </button>
        </Sheet>

        {/* Header ⋯ */}
        <ActionSheet
          open={headerMenu}
          onClose={() => setHeaderMenu(false)}
          actions={[
            { label: "Тип заказа", onClick: () => { setHeaderMenu(false); setOrderTypeSheet(true); } },
            { label: "Скидки и надбавки", onClick: () => { setHeaderMenu(false); showToast("Скидки и надбавки — скоро"); } },
            { label: `Сортировать по курсам${sortByCourse ? " ✓" : ""}`, onClick: () => { const next = !sortByCourse; setSortByCourse(next); setHeaderMenu(false); showToast(next ? "Отсортировано по курсам" : "Сортировка по курсам выключена"); } },
          ]}
        />

        {/* Тип заказа */}
        <ActionSheet
          open={orderTypeSheet}
          onClose={() => setOrderTypeSheet(false)}
          header="Тип заказа"
          actions={([["hall", "В зале"], ["takeaway", "На вынос"], ["delivery", "Доставка"]] as [string, string][]).map(([v, label]) => ({
            label: `${label}${orderType === v ? " ✓" : ""}`,
            tone: orderType === v ? ("primary" as const) : undefined,
            onClick: () => { setOrderType(v); setOrderTypeSheet(false); showToast(`Тип: ${label}`); },
          }))}
        />

        {/* Количество */}
        <Sheet open={!!qtyEdit} onClose={() => setQtyEdit(null)} title="Количество">
          {qtyEdit && (
            <>
              <input
                autoFocus
                inputMode="numeric"
                type="text"
                value={qtyEdit.value}
                onChange={(e) => setQtyEdit({ ...qtyEdit, value: e.target.value.replace(/[^0-9]/g, "") })}
                className="w-full bg-inset rounded-2xl px-4 py-4 text-lg font-semibold text-ink outline-none mb-4"
              />
              <button
                onClick={async () => {
                  const { clientId, dishId, current, value } = qtyEdit;
                  const n = Math.max(0, parseInt(value, 10) || 0);
                  setQtyEdit(null);
                  if (n === current) return;
                  try {
                    if (n === 0) await removeBasketDish(clientId, dishId);
                    else await modifyBasket(clientId, dishId, n - current);
                    refreshGuest(clientId);
                  } catch { showToast("Не удалось изменить количество", "err"); }
                }}
                className="w-full py-4 rounded-2xl bg-blue-500 text-white font-bold text-base active:scale-[0.98] transition"
              >
                Готово
              </button>
            </>
          )}
        </Sheet>

        {/* Курс подачи */}
        <ActionSheet
          open={!!courseFor}
          onClose={() => setCourseFor(null)}
          header="Курс подачи"
          actions={courseFor ? [
            ...["1", "2", "3", "4", "vip"].map((v) => ({
              label: v === "vip" ? "VIP" : `Курс ${v}`,
              onClick: () => {
                const ck = `${courseFor.clientId}-${courseFor.dishId}`;
                setCourses((prev) => ({ ...prev, [ck]: v }));
                setCourseFor(null);
              },
            })),
            { label: "Без курса", onClick: () => {
                const ck = `${courseFor.clientId}-${courseFor.dishId}`;
                setCourses((prev) => { const n = { ...prev }; delete n[ck]; return n; });
                setCourseFor(null);
              } },
          ] : []}
        />

        {/* Guest ⋯ */}
        <ActionSheet
          open={guestMenuFor !== null}
          onClose={() => setGuestMenuFor(null)}
          header={guests.find((x) => x.client_id === guestMenuFor)?.name}
          actions={(() => {
            const g = guests.find((x) => x.client_id === guestMenuFor);
            if (!g) return [];
            return [
              { label: "Переименовать", onClick: () => { setRenameGuest({ clientId: g.client_id, value: g.name }); setGuestMenuFor(null); } },
              { label: "Пречек", onClick: () => { setGuestMenuFor(null); print(); } },
              { label: "Перенести в новый заказ", onClick: () => { setGuestMenuFor(null); showToast("Перенос в новый заказ — скоро"); } },
              { label: "Удалить", tone: "danger" as const, onClick: () => { setGuestMenuFor(null); removeGuest(g.client_id); } },
            ];
          })()}
        />

        {/* Имя гостя */}
        <Sheet open={!!renameGuest} onClose={() => setRenameGuest(null)} title="Имя гостя">
          {renameGuest && (
            <>
              <input
                autoFocus
                type="text"
                value={renameGuest.value}
                onChange={(e) => setRenameGuest({ ...renameGuest, value: e.target.value })}
                className="w-full bg-inset rounded-2xl px-4 py-4 text-lg font-semibold text-ink outline-none mb-4"
              />
              <button
                onClick={() => {
                  applyRename(renameGuest.clientId, renameGuest.value);
                  setRenameGuest(null);
                }}
                className="w-full py-4 rounded-2xl bg-blue-500 text-white font-bold text-base active:scale-[0.98] transition"
              >
                Готово
              </button>
            </>
          )}
        </Sheet>

        {/* Modifiers Modal */}
        {addDish.modifiersDish && (
          <ModifiersModal
            dishName={addDish.modifiersDish.name}
            groups={addDish.modifierGroups}
            selections={addDish.modSelections}
            onSelect={(id, a) => addDish.setModSelections((prev) => ({ ...prev, [id]: a }))}
            editing={!!addDish.editingModFor}
            onConfirm={addDish.confirm}
            onClose={addDish.close}
          />
        )}

        {/* Dish Comment Modal */}
        {editingComment && (
          <div className="fixed inset-0 z-50 bg-black/60 flex items-end justify-center" onClick={() => setEditingComment(null)}>
            <div className="bg-surface w-full max-w-lg rounded-t-3xl p-5" onClick={(e) => e.stopPropagation()}>
              <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
              <h2 className="text-lg font-bold text-ink mb-3">Комментарий к блюду</h2>
              <textarea
                autoFocus
                value={editingComment.value}
                onChange={(e) => setEditingComment({ ...editingComment, value: e.target.value })}
                maxLength={255}
                rows={3}
                placeholder="Без лука, аллергия на орехи..."
                className="w-full px-3 py-3 bg-inset border border-hair rounded-xl text-sm text-ink placeholder-gray-400 focus:outline-none focus:border-black transition resize-none"
              />
              <p className="text-xs text-ink-subtle text-right mt-1">{editingComment.value.length}/255</p>
              <div className="flex gap-3 mt-4">
                <button onClick={() => setEditingComment(null)} className="flex-1 py-3 rounded-xl border border-hair text-ink-muted font-semibold hover:bg-inset transition">Отмена</button>
                <button
                  onClick={async () => {
                    try {
                      await modifyBasket(editingComment.clientId, editingComment.dishId, 0, undefined, editingComment.value);
                      refreshGuest(editingComment.clientId);
                      setEditingComment(null);
                      showToast("Комментарий сохранён");
                    } catch {
                      showToast("Ошибка сохранения", "err");
                    }
                  }}
                  className="flex-1 py-3 rounded-xl bg-black text-white font-semibold active:scale-[0.98] transition shadow-md"
                >Сохранить</button>
              </div>
            </div>
          </div>
        )}
        <Toast toast={toast} />

        {showQRScanner && (
          <QRScannerModal
            onClose={() => setShowQRScanner(false)}
            onCheckin={() => { checkin(); setShowQRScanner(false); }}
          />
        )}
      </div>
    );
}

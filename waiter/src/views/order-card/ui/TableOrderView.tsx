"use client";

import { useState, useMemo, type ReactNode } from "react";
import { ChevronDown, ChevronLeft, Search, X, ScanLine, Send, Eye, QrCode, Ellipsis, Trash2, ArrowRight, ArrowLeftRight, Split, Check, Minus, Plus } from "lucide-react";
import { Toast } from "@/shared/ui/Toast";
import { useToast } from "@/shared/lib/use-toast";
import { Sheet, ActionSheet } from "@/shared/ui/Sheet";
import { BackButton } from "@/shared/ui/BackButton";
import { IconButton } from "@/shared/ui/IconButton";
import { Button } from "@/shared/ui/button";
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
import { GuestProgressBar } from "@/features/gamification";

// Круглая кнопка нижней панели режима выделения (iiko): 5 действий одной формы.
function SelectToolbarButton({
  onClick,
  disabled,
  primary = false,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-11 h-11 rounded-full flex items-center justify-center active:scale-90 transition disabled:opacity-30 ${primary ? "bg-blue-500 text-white shadow-md" : "bg-inset text-ink"}`}
    >
      {children}
    </button>
  );
}

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

  // Menu panel toggle — open on entry: the waiter always starts by picking dishes
  const [menuCollapsed, setMenuCollapsed] = useState(false);
  // Guest-row ⋯ action sheet + rename modal
  const [guestMenuFor, setGuestMenuFor] = useState<number | null>(null);
  const [renameGuest, setRenameGuest] = useState<{ clientId: number; value: string } | null>(null);
  // Dish quantity popup (enter number) + course picker (local only — backend has no course field)
  const [qtyEdit, setQtyEdit] = useState<{ clientId: number; dishId: number; current: number; value: string; name: string } | null>(null);
  const [courseFor, setCourseFor] = useState<{ clientId: number; dishId: number } | null>(null);
  // Split picker: the dish held by `sourceCid` is split among the checked guests.
  const [splitFor, setSplitFor] = useState<{ sourceCid: number; dishId: number; name: string } | null>(null);
  const [splitTargets, setSplitTargets] = useState<Set<number>>(new Set());
  // Multi-select (iiko long-press) mode. Keys are `${clientId}:${dishId}`.
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const selKey = (cid: number, dishId: number) => `${cid}:${dishId}`;
  const courseKey = (cid: number, dishId: number) => `${cid}:${dishId}`;
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

  // dish_id → menu category (basket items don't carry it) — for the gamification bar.
  const dishCategory = useMemo(() => {
    const m = new Map<number, string>();
    for (const cat of menu) for (const d of cat.dishes) m.set(d.id, cat.category_name);
    return m;
  }, [menu]);

  // The SAME search + send bar, rendered either above the expanded menu (iiko)
  // or pinned to the bottom when the menu is collapsed.
  const renderSearchBar = (atTop: boolean) => (
    <div className={`shrink-0 bg-surface px-3 border-t-2 border-hair shadow-[0_-2px_8px_rgba(0,0,0,0.06)] ${atTop ? "pb-2" : "pb-8"}`}>
      {/* Один хендл на оба состояния: ↑ раскрывает меню, ↓ сворачивает его обратно вниз */}
      <button
        onClick={() => setMenuCollapsed(!menuCollapsed)}
        aria-label={atTop ? "Свернуть меню" : "Открыть меню"}
        className="w-full flex justify-center py-1 active:bg-inset transition"
      >
        <ChevronDown className={`h-5 w-6 text-ink-subtle ${atTop ? "" : "rotate-180"}`} strokeWidth={2.5} />
      </button>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          {/* Слева: лупа, либо стрелка «назад ко всему меню», когда открыта категория или идёт поиск */}
          {atTop && (menuSearch || activeMenuCategory) ? (
            <button
              onClick={() => { setMenuSearch(""); setActiveMenuCategory(null); }}
              aria-label="Все категории"
              className="absolute left-1 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-ink active:scale-90 transition"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
          ) : (
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-subtle" />
          )}
          <input
            type="text"
            value={menuSearch}
            onChange={(e) => { setMenuSearch(e.target.value); setMenuCollapsed(false); }}
            onFocus={() => setMenuCollapsed(false)}
            placeholder="Поиск позиций"
            className={`w-full py-3 bg-inset rounded-full text-sm text-ink placeholder-gray-500 focus:outline-none ${menuSearch ? "pr-20" : "pr-11"} ${atTop && (menuSearch || activeMenuCategory) ? "pl-10" : "pl-9"}`}
          />
          {/* Крестик — только сбрасывает текст поиска, не трогает категорию */}
          {menuSearch && (
            <button onClick={() => setMenuSearch("")} aria-label="Очистить поиск" className="absolute right-10 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-ink-muted active:scale-90 transition">
              <X className="h-4 w-4" strokeWidth={2.5} />
            </button>
          )}
          <button onClick={() => setShowQRScanner(true)} aria-label="Сканировать" className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-ink-muted active:scale-90 transition">
            <ScanLine className="h-5 w-5" />
          </button>
        </div>
        {/* Отправить — в обоих состояниях; меню сворачивается стрелкой сверху */}
        <button
          onClick={() => setSendSheet(true)}
          disabled={totalDishes === 0}
          aria-label="Отправить"
          className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center shadow-md active:scale-95 transition disabled:opacity-40 bg-blue-500 text-white"
        >
          <Send className="h-6 w-6 -ml-1" />
        </button>
      </div>
    </div>
  );

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
              <Eye className="h-5 w-5" />
            </IconButton>
            <IconButton ariaLabel="Сканировать" onClick={() => setShowQRScanner(true)}>
              <QrCode className="h-5 w-5" />
            </IconButton>
            <IconButton ariaLabel="Меню заказа" onClick={() => setHeaderMenu(true)}>
              <Ellipsis className="h-5 w-5" strokeWidth={2.5} />
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
                    const rank = (id: number) => { const c = courses[courseKey(guest.client_id, id)]; return c === "vip" ? 5 : c ? parseInt(c, 10) : 6; };
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
                    showPlus={menuCollapsed}
                    onSelect={() => { setActiveGuestIdx(idx); setMenuCollapsed(false); }}
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
                            course={courses[courseKey(guest.client_id, item.dish_id)] || "1"}
                            warn={warn}
                            onQty={() => setQtyEdit({ clientId: guest.client_id, dishId: item.dish_id, current: item.quantity, value: String(item.quantity), name: item.dish_name })}
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
                  {/* Наполненность чека по коэффициентам (per-guest, динамически) */}
                  <GuestProgressBar categories={items.map((i) => dishCategory.get(i.dish_id)).filter((c): c is string => !!c)} />
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

        {/* Строка поиска всегда прямо над меню: раскрытое меню уходит под неё,
            свёрнутое — прижимает её к низу экрана (iiko) */}
        {!selecting && renderSearchBar(!menuCollapsed)}

        {/* Inline menu (widget) */}
        {!selecting && !menuCollapsed && (
          <MenuPanel
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
        )}

        {/* Bottom action bar in selection mode (iiko): delete · split · send-to-kitchen */}
        {selecting && (
          <div className="shrink-0 bg-surface border-t border-hair px-4 pt-3 pb-8 shadow-[0_-4px_20px_rgba(0,0,0,0.06)] flex items-center justify-around">
            {/* Удалить */}
            <SelectToolbarButton onClick={deleteSelected} disabled={selected.size === 0}>
              <Trash2 className="h-5 w-5" />
            </SelectToolbarButton>
            {/* Перенести в новый заказ (нужен бэкенд переноса между заказами) */}
            <SelectToolbarButton onClick={() => { if (selected.size === 0) return; showToast("Перенос в новый заказ — скоро"); }} disabled={selected.size === 0}>
              <ArrowRight className="h-5 w-5" />
            </SelectToolbarButton>
            {/* Разделить — только 1 блюдо и 2+ гостя */}
            <SelectToolbarButton onClick={splitSelected} disabled={selected.size !== 1 || guests.length < 2}>
              <Split className="h-5 w-5" />
            </SelectToolbarButton>
            {/* Перенести в другой заказ / стол (нужен бэкенд перемещения между столами) */}
            <SelectToolbarButton onClick={() => { if (selected.size === 0) return; showToast("Перенос в другой заказ — скоро"); }} disabled={selected.size === 0}>
              <ArrowLeftRight className="h-5 w-5" />
            </SelectToolbarButton>
            {/* Отправить на кухню — ключевая: только выбранные блюда */}
            <SelectToolbarButton onClick={sendSelected} disabled={selected.size === 0} primary>
              <Send className="h-5 w-5 -ml-1" />
            </SelectToolbarButton>
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
                    {on && <Check className="h-4 w-4 text-white" strokeWidth={3} />}
                  </span>
                  <span className="flex-1 text-left text-sm font-semibold text-ink">{g.name?.trim() || `Гость ${i + 1}`}{isOwner && <span className="text-ink-subtle font-normal"> · владелец</span>}</span>
                </button>
              );
            })}
          </div>
          <Button variant="primary" size="lg" fullWidth onClick={doSplit} disabled={splitTargets.size !== 2}>
            {splitTargets.size === 2 ? "Разделить" : "Отметьте 2 гостей"}
          </Button>
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
        <Sheet open={!!qtyEdit} onClose={() => setQtyEdit(null)} title="Количество" subtitle={qtyEdit?.name}>
          {qtyEdit && (
            <>
              {/* iiko: одна пилюля — число слева, сегмент − | + справа */}
              <div className="flex items-center gap-3 h-16 pl-5 pr-1 rounded-full bg-inset mb-6">
                <input
                  autoFocus
                  inputMode="numeric"
                  type="text"
                  value={qtyEdit.value}
                  onChange={(e) => setQtyEdit({ ...qtyEdit, value: e.target.value.replace(/[^0-9]/g, "") })}
                  aria-label="Количество"
                  className="flex-1 min-w-0 bg-transparent text-2xl font-semibold text-ink outline-none"
                />
                <div className="flex items-center h-12 rounded-full bg-surface shadow-sm overflow-hidden flex-shrink-0">
                  <button
                    onClick={() => setQtyEdit({ ...qtyEdit, value: String(Math.max(0, (parseInt(qtyEdit.value, 10) || 0) - 1)) })}
                    disabled={(parseInt(qtyEdit.value, 10) || 0) <= 0}
                    aria-label="Уменьшить"
                    className="w-14 h-12 flex items-center justify-center text-ink-muted active:bg-inset transition disabled:opacity-30"
                  >
                    <Minus className="h-5 w-5" strokeWidth={2.5} />
                  </button>
                  <span className="w-px h-6 bg-hair flex-shrink-0" />
                  <button
                    onClick={() => setQtyEdit({ ...qtyEdit, value: String((parseInt(qtyEdit.value, 10) || 0) + 1) })}
                    aria-label="Увеличить"
                    className="w-14 h-12 flex items-center justify-center text-blue-500 active:bg-inset transition"
                  >
                    <Plus className="h-5 w-5" strokeWidth={2.5} />
                  </button>
                </div>
              </div>
              <Button
                variant="primary"
                size="lg"
                fullWidth
                className="rounded-full"
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
              >
                Готово
              </Button>
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
                const ck = courseKey(courseFor.clientId, courseFor.dishId);
                setCourses((prev) => ({ ...prev, [ck]: v }));
                setCourseFor(null);
              },
            })),
            { label: "Без курса", onClick: () => {
                const ck = courseKey(courseFor.clientId, courseFor.dishId);
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
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => {
                  applyRename(renameGuest.clientId, renameGuest.value);
                  setRenameGuest(null);
                }}
              >
                Готово
              </Button>
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
        <Sheet open={!!editingComment} onClose={() => setEditingComment(null)} title="Комментарий к блюду">
          {editingComment && (
            <>
              <textarea
                autoFocus
                value={editingComment.value}
                onChange={(e) => setEditingComment({ ...editingComment, value: e.target.value })}
                maxLength={255}
                rows={3}
                placeholder="Без лука, аллергия на орехи..."
                className="w-full px-3 py-3 bg-surface border border-hair rounded-xl text-sm text-ink placeholder-gray-400 focus:outline-none focus:border-black transition resize-none"
              />
              <p className="text-xs text-ink-subtle text-right mt-1">{editingComment.value.length}/255</p>
              <div className="flex gap-3 mt-4">
                <Button variant="outline" size="md" fullWidth onClick={() => setEditingComment(null)}>Отмена</Button>
                <Button
                  variant="dark"
                  size="md"
                  fullWidth
                  className="shadow-md"
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
                >Сохранить</Button>
              </div>
            </>
          )}
        </Sheet>
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

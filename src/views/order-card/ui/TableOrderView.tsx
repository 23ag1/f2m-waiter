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
import { modifyBasket, removeBasketDish } from "@/shared/api";
import { DISH_INGREDIENTS, RecommendationCard } from "@/entities/recommendation";
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
    guests, guestBaskets, guestHints, guestDismissed,
    activeGuestIdx, setActiveGuestIdx, setGuestDismissed,
    refreshGuest, setGuestHunger, addHintDishLocally, checkin, addGuest, removeGuest, renameGuest: applyRename,
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
        {/* Header — iiko style */}
        <header className="shrink-0 bg-inset px-3 pt-3 pb-2 flex items-center gap-3 z-10">
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
                            onSplit={() => { if (guests.length > 1) showToast("Разделить — скоро"); else showToast("Нет других гостей для разделения", "err"); }}
                            onRemove={async () => { await removeBasketDish(guest.client_id, item.dish_id); refreshGuest(guest.client_id); }}
                          />
                        );
                      })}
                    </div>
                  )}
                  {/* Inline hint strip per guest (рекомендации) */}
                  {(() => {
                    const dismissed = guestDismissed[guest.client_id] ?? new Set<number>();
                    const gHints = (guestHints[guest.client_id] ?? []).filter(h => !dismissed.has(h.id));
                    if (gHints.length === 0) return null;
                    return (
                      <div className="overflow-x-auto px-4 py-2 bg-amber-50/40 border-t border-amber-100">
                        <div className="flex gap-2 w-max">
                          {gHints.map((hint) => (
                            <RecommendationCard
                              key={hint.id}
                              hint={hint}
                              onAdd={() => addHintDishLocally(guest.client_id, hint, guest.hunger, guestRestrictions(guest), guest.checkedIn)}
                              onDismiss={() => setGuestDismissed((prev) => ({ ...prev, [guest.client_id]: new Set([...(prev[guest.client_id] ?? []), hint.id]) }))}
                            />
                          ))}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              );
            })}
          </div>
          <div className="flex justify-center py-4 border-t border-dashed border-hair">
            <button
              onClick={addGuest}
              className="px-6 py-2.5 rounded-full bg-surface border border-hair shadow-sm text-sm font-bold text-blue-500 active:scale-95 transition"
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

        {/* Bottom bar — search + send (iiko) */}
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

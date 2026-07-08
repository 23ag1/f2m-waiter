"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { Toast } from "@/shared/ui/Toast";
import { useToast } from "@/shared/lib/use-toast";
import { useRouter } from "next/navigation";
import { getActiveTables, closeTable, getIikoTables, printBill, changeTable as apiChangeTable, mergeOrders as apiMergeOrders } from "@/shared/api";
import type { IikoTable } from "@/views/new-order/model/types";
import { getCookie, deleteCookie } from "@/shared/lib/cookies";
import { OrdersList } from "@/widgets/orders-list";
import type { ActiveTable } from "@/entities/table";
import { ProfileSheet } from "@/widgets/profile";
import { ContextMenu, type ContextMenuItem } from "@/shared/ui/ContextMenu";
import { ActionSheet, Sheet } from "@/shared/ui/Sheet";
import { Avatar } from "@/shared/ui/Avatar";
import { IconButton } from "@/shared/ui/IconButton";
import { SegmentedControl } from "@/shared/ui/SegmentedControl";
import {
  PaymentSheet,
  WaiterPickerSheet,
  OrderCommentSheet,
  RenameOrderSheet,
  PrecheckSheet,
} from "@/features/order-actions";
import { useTourPhase, startTour, hasCompletedTour } from "@/features/onboarding";

type TabType = "mine" | "all" | "external";
type SortKey = "time_desc" | "time_asc" | "table" | "amount";

const SORT_LABELS: Record<SortKey, string> = {
  time_desc: "Сначала новые",
  time_asc: "Сначала старые",
  table: "По номеру стола",
  amount: "По сумме (убыв.)",
};

const orderTime = (t: ActiveTable) => new Date((t.created_at || "").replace(" ", "T")).getTime() || 0;

function sortTables(list: ActiveTable[], key: SortKey): ActiveTable[] {
  const arr = [...list];
  switch (key) {
    case "time_asc": return arr.sort((a, b) => orderTime(a) - orderTime(b));
    case "time_desc": return arr.sort((a, b) => orderTime(b) - orderTime(a));
    case "table": return arr.sort((a, b) => (Number(a.table_number) || 0) - (Number(b.table_number) || 0));
    case "amount": return arr.sort((a, b) => b.total_price - a.total_price);
    default: return arr;
  }
}

// Icons for the long-press card menu (iiko-style).
const IcoPay = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>);
const IcoWaiter = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>);
const IcoComment = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>);
const IcoRename = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>);
const IcoPrint = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a1 1 0 001-1v-4a1 1 0 00-1-1H9a1 1 0 00-1 1v4a1 1 0 001 1zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" /></svg>);
const IcoTrash = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>);
const IcoSwapTable = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" /></svg>);
const IcoMerge = (<svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h8a2 2 0 012 2v3m0 0l-2.5-2.5M18 12l2.5-2.5M6 17H4a2 2 0 01-2-2V5a2 2 0 012-2h4m6 18h4a2 2 0 002-2v-4" /></svg>);

export function OrdersView() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [tables, setTables] = useState<ActiveTable[]>([]);
  const [loadingTables, setLoadingTables] = useState(true);
  const [closingId, setClosingId] = useState<number | null>(null);
  const [confirmClose, setConfirmClose] = useState<number | null>(null);
  const [cardMenu, setCardMenu] = useState<{ table: ActiveTable; anchor: { x: number; y: number } } | null>(null);
  // Which order-action sheet is open, and for which order.
  const [action, setAction] = useState<{ type: "pay" | "waiter" | "comment" | "rename" | "precheck"; table: ActiveTable } | null>(null);
  const [printing, setPrinting] = useState(false);
  // Local (frontend-only) overrides — no backend fields for these yet.
  const [nameOverrides, setNameOverrides] = useState<Record<number, string>>({});
  const [orderComments, setOrderComments] = useState<Record<number, string>>({});
  const [waiterByTable, setWaiterByTable] = useState<Record<number, string>>({});
  const [sortBy, setSortBy] = useState<SortKey>("time_desc");
  const [sortSheet, setSortSheet] = useState(false);
  const [menuSheet, setMenuSheet] = useState(false);
  const { toast, showToast } = useToast();
  const [tab, setTab] = useState<TabType>("mine");
  const [showProfile, setShowProfile] = useState(false);
  const tourPhase = useTourPhase();
  const profileOpen = showProfile || tourPhase === "profile" || tourPhase === "recset";

  // Auto-run the onboarding tour on the very first visit.
  useEffect(() => {
    if (!hasCompletedTour()) startTour();
  }, []);
  const [tick, setTick] = useState(0);
  // table_number → section_name mapping from iiko
  const [sectionMap, setSectionMap] = useState<Record<string, string>>({});
  const [iikoTables, setIikoTables] = useState<IikoTable[]>([]);
  // "Поменять стол" / "Объединить заказы" pickers (act on the chosen order)
  const [changeTableFor, setChangeTableFor] = useState<ActiveTable | null>(null);
  const [mergeFor, setMergeFor] = useState<ActiveTable | null>(null);

  useEffect(() => {
    const t = getCookie("waiter_token");
    if (!t) router.push("/");
    else setToken(t);
  }, [router]);

  const fetchTables = useCallback(async () => {
    try {
      const data = await getActiveTables();
      setTables(data.tables || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingTables(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    fetchTables();
    const interval = setInterval(fetchTables, 15000);
    // Load iiko section mapping + full table list once (for the change-table picker)
    getIikoTables().then((data) => {
      const list: IikoTable[] = data.tables || [];
      setIikoTables(list);
      const map: Record<string, string> = {};
      for (const t of list) map[String(t.number)] = t.section_name || "Зал";
      setSectionMap(map);
    }).catch(() => {});
    return () => clearInterval(interval);
  }, [token, fetchTables]);

  // Tick every 30s to update timers
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 30000);
    return () => clearInterval(t);
  }, []);

  const handleClose = async (tableId: number) => {
    setClosingId(tableId);
    try {
      await closeTable(tableId);
      setTables((prev) => prev.filter((t) => t.id !== tableId));
      showToast("Стол закрыт");
    } catch {
      showToast("Не удалось закрыть стол", "err");
    }
    setClosingId(null);
    setConfirmClose(null);
  };

  const orderClientId = (t: ActiveTable) => t.guests?.[0]?.client_id ?? t.client_id;

  // Move the order to a different table (backend endpoint pending — front is ready).
  const doChangeTable = async (target: IikoTable) => {
    const order = changeTableFor;
    setChangeTableFor(null);
    if (!order) return;
    try {
      await apiChangeTable(order.id, target.id, String(target.number));
      showToast(`Заказ перенесён на стол ${target.number}`);
      fetchTables();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Перенос стола — нужен бэкенд", "err");
    }
  };

  // Merge this order with another active order (backend endpoint pending).
  const doMerge = async (target: ActiveTable) => {
    const order = mergeFor;
    setMergeFor(null);
    if (!order) return;
    try {
      await apiMergeOrders(order.id, target.id);
      showToast(`Заказы столов ${order.table_number} и ${target.table_number} объединены`);
      fetchTables();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Объединение — нужен бэкенд", "err");
    }
  };

  const handlePaid = async (table: ActiveTable) => {
    setAction(null);
    try {
      await closeTable(table.id);
      setTables((prev) => prev.filter((t) => t.id !== table.id));
      showToast("Заказ оплачен и закрыт");
    } catch {
      showToast("Не удалось провести оплату", "err");
    }
  };

  const handlePrint = async (table: ActiveTable) => {
    setPrinting(true);
    try {
      await printBill(orderClientId(table), table.table_number);
      showToast("Пречек отправлен на печать");
      setAction(null);
    } catch {
      showToast("Не удалось распечатать", "err");
    } finally {
      setPrinting(false);
    }
  };

  if (!token) return <div className="p-4">Загрузка...</div>;

  const displayTables = tab === "external" ? [] : sortTables(tables, sortBy);

  const cardMenuItems: ContextMenuItem[] = cardMenu ? [
    { label: "Оплатить", icon: IcoPay, onClick: () => setAction({ type: "pay", table: cardMenu.table }) },
    { label: "Сменить официанта", icon: IcoWaiter, onClick: () => setAction({ type: "waiter", table: cardMenu.table }) },
    { label: "Поменять стол", icon: IcoSwapTable, onClick: () => { const t = cardMenu.table; setCardMenu(null); setChangeTableFor(t); } },
    { label: "Объединить заказы", icon: IcoMerge, onClick: () => { const t = cardMenu.table; setCardMenu(null); setMergeFor(t); } },
    { label: "Комментарий", icon: IcoComment, onClick: () => setAction({ type: "comment", table: cardMenu.table }) },
    { label: "Переименовать", icon: IcoRename, onClick: () => setAction({ type: "rename", table: cardMenu.table }) },
    { label: "Распечатать пречек", icon: IcoPrint, onClick: () => setAction({ type: "precheck", table: cardMenu.table }) },
    { label: "Удалить", icon: IcoTrash, tone: "danger", onClick: () => setConfirmClose(cardMenu.table.id) },
  ] : [];

  return (
    <div className="min-h-screen bg-app">
      {/* iiko-style header (large title, grey background, white pills) */}
      <header className="bg-inset pt-2">
        {/* Top row: avatar | tabs pill | icons pill */}
        <div className="flex items-center gap-2 px-3 py-2">
          <span data-tour="avatar" className="inline-flex rounded-full">
            <Avatar initial="W" size="md" onClick={() => setShowProfile(true)} />
          </span>

          {/* Segmented tabs — white pill, selected tab highlighted grey */}
          <SegmentedControl<TabType>
            className="flex-1 shadow-sm"
            variant="inset"
            options={[{ value: "mine", label: "Мои" }, { value: "all", label: "Все" }, { value: "external", label: "Внеш…" }]}
            value={tab}
            onChange={setTab}
          />

          {/* Icons — separate white pill */}
          <div className="flex items-center bg-surface rounded-full shadow-sm px-1 flex-shrink-0">
            <IconButton size="tall" ariaLabel="Сортировка" onClick={() => setSortSheet(true)}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" />
              </svg>
            </IconButton>
            <IconButton size="tall" ariaLabel="Меню" onClick={() => setMenuSheet(true)}>
              <span className="w-7 h-7 rounded-full border-2 border-current flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 12h.01M12 12h.01M19 12h.01" />
                </svg>
              </span>
            </IconButton>
          </div>
        </div>

        {/* Large title */}
        <div className="px-4 pt-1 pb-3">
          <h1 className="text-4xl font-extrabold text-ink tracking-tight">Заказы</h1>
        </div>
      </header>

      <main className="px-3 py-3 pb-28">
        {loadingTables && displayTables.length === 0 && (
          <div className="flex items-center justify-center p-12 text-ink-subtle">
            <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Загрузка...
          </div>
        )}

        {!loadingTables && displayTables.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-ink-subtle">
            <p className="text-lg font-bold text-ink mb-1">Заказов пока нет</p>
            <p className="text-sm">Нажмите на «+», чтобы создать новый заказ</p>
          </div>
        )}

        {displayTables.length > 0 && (
          <OrdersList
            tables={displayTables}
            sectionMap={sectionMap}
            nameOverrides={nameOverrides}
            onCardLongPress={(table, anchor) => setCardMenu({ table, anchor })}
          />
        )}
      </main>

      {/* Long-press card menu (iiko) */}
      {cardMenu && (
        <ContextMenu anchor={cardMenu.anchor} items={cardMenuItems} onClose={() => setCardMenu(null)} />
      )}

      {/* Поменять стол — table picker (Мои столы + залы), iiko-style */}
      <Sheet open={!!changeTableFor} onClose={() => setChangeTableFor(null)} title="Поменять стол">
        {(() => {
          const mine = new Set(tables.map((t) => String(t.table_number)));
          const sections = iikoTables.reduce<Record<string, IikoTable[]>>((acc, t) => {
            (acc[t.section_name || "Зал"] ||= []).push(t); return acc;
          }, {});
          const myTiles = iikoTables.filter((t) => mine.has(String(t.number)));
          const tile = (t: IikoTable) => {
            const isCurrent = changeTableFor && String(t.number) === String(changeTableFor.table_number);
            const isMine = mine.has(String(t.number));
            return (
              <button key={t.id} onClick={() => doChangeTable(t)}
                className={`h-12 rounded-xl flex items-center justify-center font-bold text-sm active:scale-95 transition ${isCurrent ? "bg-blue-500 text-white" : isMine ? "bg-inset text-ink border border-hair" : "bg-surface text-ink border border-hair"}`}>
                {t.number}
              </button>
            );
          };
          return (
            <div className="max-h-[55vh] overflow-y-auto space-y-4 pb-2">
              {myTiles.length > 0 && (
                <div>
                  <p className="text-xs font-bold text-ink-muted mb-2">Мои столы</p>
                  <div className="grid grid-cols-5 gap-2">{myTiles.map(tile)}</div>
                </div>
              )}
              {Object.entries(sections).map(([name, ts]) => (
                <div key={name}>
                  <p className="text-xs font-bold text-ink-muted mb-2">{name}</p>
                  <div className="grid grid-cols-5 gap-2">{ts.map(tile)}</div>
                </div>
              ))}
              {iikoTables.length === 0 && <p className="text-center text-ink-subtle py-6 text-sm">Загрузка столов…</p>}
            </div>
          );
        })()}
      </Sheet>

      {/* Объединить заказы — pick another active order to merge into */}
      <Sheet open={!!mergeFor} onClose={() => setMergeFor(null)} title="Объединить с заказом">
        <div className="max-h-[55vh] overflow-y-auto space-y-2 pb-2">
          {tables.filter((t) => t.id !== mergeFor?.id).map((t) => (
            <button key={t.id} onClick={() => doMerge(t)}
              className="w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-inset border border-hair active:scale-[0.99] transition text-left">
              <div className="min-w-0">
                <p className="text-sm font-bold text-ink">Стол {t.table_number}</p>
                <p className="text-xs text-ink-subtle truncate">{(t.dish_names || []).slice(0, 2).join(", ") || "—"}</p>
              </div>
              <span className="text-sm font-semibold text-ink flex-shrink-0">{Number(t.total_price).toLocaleString("ru-RU")} ₽</span>
            </button>
          ))}
          {tables.filter((t) => t.id !== mergeFor?.id).length === 0 && (
            <p className="text-center text-ink-subtle py-6 text-sm">Нет других активных заказов</p>
          )}
        </div>
      </Sheet>

      {/* Sort sheet (↑↓) */}
      <ActionSheet
        open={sortSheet}
        onClose={() => setSortSheet(false)}
        header="Сортировка"
        actions={(Object.keys(SORT_LABELS) as SortKey[]).map((k) => ({
          label: `${SORT_LABELS[k]}${sortBy === k ? "  ✓" : ""}`,
          tone: sortBy === k ? ("primary" as const) : undefined,
          onClick: () => { setSortBy(k); setSortSheet(false); },
        }))}
      />

      {/* Overflow menu (⋯) */}
      <ActionSheet
        open={menuSheet}
        onClose={() => setMenuSheet(false)}
        actions={[
          { label: "Обновить список", onClick: () => { setMenuSheet(false); fetchTables(); showToast("Обновлено"); } },
          { label: "Профиль", onClick: () => { setMenuSheet(false); setShowProfile(true); } },
          { label: "Выйти", tone: "danger" as const, onClick: () => { setMenuSheet(false); deleteCookie("waiter_token"); localStorage.removeItem("waiter_pin"); router.push("/"); } },
        ]}
      />

      {/* Order-action sheets */}
      <PaymentSheet
        open={action?.type === "pay"}
        onClose={() => setAction(null)}
        tableNumber={action?.table.table_number ?? ""}
        total={action?.table.total_price ?? 0}
        onPaid={() => { if (action) handlePaid(action.table); }}
      />
      <WaiterPickerSheet
        open={action?.type === "waiter"}
        onClose={() => setAction(null)}
        currentName={action ? waiterByTable[action.table.id] : undefined}
        onPick={(name) => {
          if (action) setWaiterByTable((p) => ({ ...p, [action.table.id]: name }));
          setAction(null);
          showToast(`Официант: ${name}`);
        }}
      />
      <OrderCommentSheet
        open={action?.type === "comment"}
        onClose={() => setAction(null)}
        initial={action ? (orderComments[action.table.id] ?? "") : ""}
        onSave={(value) => {
          if (action) setOrderComments((p) => ({ ...p, [action.table.id]: value }));
          setAction(null);
          showToast(value ? "Комментарий сохранён" : "Комментарий удалён");
        }}
      />
      <RenameOrderSheet
        open={action?.type === "rename"}
        onClose={() => setAction(null)}
        initial={action ? (nameOverrides[action.table.id] ?? `Стол ${action.table.table_number}`) : ""}
        onSave={(value) => {
          if (action) setNameOverrides((p) => ({ ...p, [action.table.id]: value }));
          setAction(null);
          showToast("Переименовано");
        }}
      />
      <PrecheckSheet
        open={action?.type === "precheck"}
        onClose={() => setAction(null)}
        tableNumber={action?.table.table_number ?? ""}
        guestCount={action?.table.guests?.length ?? 0}
        lines={action?.table.dish_names ?? []}
        total={action?.table.total_price ?? 0}
        printing={printing}
        onPrint={() => { if (action) handlePrint(action.table); }}
      />

      {/* FAB — new order */}
      <Link
        href="/dashboard/new-order?new=1"
        className="fixed bottom-7 right-5 w-16 h-16 bg-blue-500 rounded-full flex items-center justify-center shadow-xl active:scale-95 transition-transform z-20"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      </Link>

      {/* Profile — full-screen iiko-style */}
      <ProfileSheet
        open={profileOpen}
        onClose={() => setShowProfile(false)}
        onLogout={() => { deleteCookie("waiter_token"); localStorage.removeItem("waiter_pin"); router.push("/"); }}
        name="Официант"
        initial="W"
      />

      {/* Confirm close modal */}
      {confirmClose !== null && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40" onClick={() => setConfirmClose(null)}>
          <div className="bg-surface w-full max-w-md rounded-t-2xl p-6 pb-8" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-ink mb-2">Закрыть стол?</h3>
            <p className="text-sm text-ink-muted mb-6">Стол будет закрыт и удалён из списка.</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmClose(null)} className="flex-1 py-3 rounded-xl border border-hair text-sm font-semibold text-ink">Отмена</button>
              <button onClick={() => handleClose(confirmClose)} className="flex-1 py-3 rounded-xl bg-red-500 text-white text-sm font-semibold">Закрыть</button>
            </div>
          </div>
        </div>
      )}

      <Toast toast={toast} />
    </div>
  );
}

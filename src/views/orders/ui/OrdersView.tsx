"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { Toast } from "@/shared/ui/Toast";
import { useToast } from "@/shared/lib/use-toast";
import { useRouter } from "next/navigation";
import { getActiveTables, closeTable, getIikoTables, printBill } from "@/shared/api";
import { getCookie, deleteCookie } from "@/shared/lib/cookies";
import { OrdersList } from "@/widgets/orders-list";
import type { ActiveTable } from "@/entities/table";
import { ProfileSheet } from "@/widgets/profile";
import { ContextMenu, type ContextMenuItem } from "@/shared/ui/ContextMenu";
import { ActionSheet } from "@/shared/ui/Sheet";
import { Avatar } from "@/shared/ui/Avatar";
import {
  PaymentSheet,
  WaiterPickerSheet,
  OrderCommentSheet,
  RenameOrderSheet,
  PrecheckSheet,
} from "@/features/order-actions";

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
  const [tick, setTick] = useState(0);
  // table_number → section_name mapping from iiko
  const [sectionMap, setSectionMap] = useState<Record<string, string>>({});

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
    // Load iiko section mapping once
    getIikoTables().then((data) => {
      const map: Record<string, string> = {};
      for (const t of (data.tables || [])) {
        map[String(t.number)] = t.section_name || "Зал";
      }
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
          <Avatar initial="W" size="md" onClick={() => setShowProfile(true)} />

          {/* Segmented tabs — white pill, selected tab highlighted grey */}
          <div className="flex-1 flex bg-surface rounded-full p-1 shadow-sm">
            {(["mine", "all", "external"] as TabType[]).map((t, i) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2 text-sm font-bold rounded-full transition truncate ${
                  tab === t ? "bg-inset text-ink" : "text-ink"
                }`}
              >
                {i === 0 ? "Мои" : i === 1 ? "Все" : "Внеш…"}
              </button>
            ))}
          </div>

          {/* Icons — separate white pill */}
          <div className="flex items-center bg-surface rounded-full shadow-sm px-1 flex-shrink-0">
            <button onClick={() => setSortSheet(true)} aria-label="Сортировка" className="w-9 h-11 flex items-center justify-center text-ink active:scale-90 transition-transform">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" />
              </svg>
            </button>
            <button onClick={() => setMenuSheet(true)} aria-label="Меню" className="w-9 h-11 flex items-center justify-center text-ink active:scale-90 transition-transform">
              <span className="w-7 h-7 rounded-full border-2 border-current flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 12h.01M12 12h.01M19 12h.01" />
                </svg>
              </span>
            </button>
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
        open={showProfile}
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

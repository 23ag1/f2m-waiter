"use client";

import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import { Toast } from "@/shared/ui/Toast";
import { CloseButton } from "@/shared/ui/CloseButton";
import { useToast } from "@/shared/lib/use-toast";
import { useRouter, useSearchParams } from "next/navigation";
import {
  getIikoTables,
  getActiveTables,
  createTableSession,
  getBasket,
  sendSessionOrder,
  modifyBasket,
  getMenu,
  getDishModifiers,
  getStopList,
  getRecommendations,
} from "@/shared/api";
import type { ModifierSelection } from "@/shared/api";
import { fetchRealHints, type HintDish } from "@/entities/recommendation";
import { nextLoyaltyProfile } from "@/entities/guest";
import type { HungerLevel } from "@/shared/lib/hunger";
import type { BasketItem } from "@/entities/dish";
import type { Dish, Category, ModifierGroup } from "@/entities/menu";
import type { IikoTable, GuestSlot, WizardStep } from "../model/types";
import { TableStep } from "./steps/TableStep";
import { GuestsStep } from "./steps/GuestsStep";
import { FillStep } from "./steps/FillStep";

export function NewOrderView() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-app flex items-center justify-center text-ink-subtle">Загрузка...</div>}>
      <NewOrderPage />
    </Suspense>
  );
}

function NewOrderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Step state
  const [step, setStep] = useState<WizardStep>("table");

  // Step 1: Table selection
  const [tables, setTables] = useState<IikoTable[]>([]);
  const [tablesLoading, setTablesLoading] = useState(true);
  const [tablesError, setTablesError] = useState("");
  const [selectedTable, setSelectedTable] = useState<IikoTable | null>(null);
  const [tableSearch, setTableSearch] = useState("");

  // Step 2: Guest count & order type
  const [guestsCount, setGuestsCount] = useState(1);
  const [orderType, setOrderType] = useState<"new" | "add">("new");

  // Step 3: Fill guests
  const [sessionTableId, setSessionTableId] = useState<number | null>(null);
  const [guestSlots, setGuestSlots] = useState<GuestSlot[]>([]);
  const [activeGuestIdx, setActiveGuestIdx] = useState(0);
  const [sessionLoading, setSessionLoading] = useState(false);

  // Step 4: Sending
  const [sending, setSending] = useState(false);

  // Order comment
  const [orderComment, setOrderComment] = useState("");
  // Per-dish comment editing
  const [editingComment, setEditingComment] = useState<{ clientId: number; dishId: number; value: string } | null>(null);

  // Toast
  const { toast, showToast } = useToast();

  // Hints (mock)
  const [guestHints, setGuestHints] = useState<Record<number, HintDish[]>>({});
  const [guestDismissed, setGuestDismissed] = useState<Record<number, Set<number>>>({});

  // Recommendations popup
  const [recsPopup, setRecsPopup] = useState<{ clientId: number; name: string; items: { name: string; price: number; category: string }[]; loading: boolean } | null>(null);
  const openRecs = async (guestClientId: number, guestName: string) => {
    setRecsPopup({ clientId: guestClientId, name: guestName, items: [], loading: true });
    try {
      const data = await getRecommendations(guestClientId);
      setRecsPopup({ clientId: guestClientId, name: guestName, items: data.recommendations || [], loading: false });
    } catch {
      setRecsPopup({ clientId: guestClientId, name: guestName, items: [], loading: false });
    }
  };

  // Per-guest baskets (client_id -> items)
  const [guestBaskets, setGuestBaskets] = useState<Record<number, BasketItem[]>>({});
  const [basketsLoading, setBasketsLoading] = useState<Record<number, boolean>>({});

  // Inline menu state
  const [menu, setMenu] = useState<Category[]>([]);
  const [menuLoading, setMenuLoading] = useState(true);
  const [stoppedIds, setStoppedIds] = useState<Set<number>>(new Set());
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());

  // Modifiers modal state
  const [modifiersDish, setModifiersDish] = useState<Dish | null>(null);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [modSelections, setModSelections] = useState<Record<string, number>>({});
  const [loadingModifiers, setLoadingModifiers] = useState(false);
  // When editing modifiers of an existing basket item: { clientId, dishId }
  const [editingModFor, setEditingModFor] = useState<{ clientId: number; dishId: number } | null>(null);

  // Track if we already handled a scan return
  const scanHandledRef = useRef(false);

  // Load basket for a specific guest
  const loadGuestBasket = useCallback(async (clientId: number, slot?: GuestSlot) => {
    setBasketsLoading((prev) => ({ ...prev, [clientId]: true }));
    try {
      const data = await getBasket(clientId);
      setGuestBaskets((prev) => ({ ...prev, [clientId]: data.basket || [] }));
    } catch {
      setGuestBaskets((prev) => ({ ...prev, [clientId]: [] }));
    } finally {
      setBasketsLoading((prev) => ({ ...prev, [clientId]: false }));
    }
    // Load hints directly — if slot passed use it, otherwise read from current state
    const s = slot;
    fetchRealHints(clientId, { hunger: s?.hunger, allergies: s?.allergies, checkedIn: s?.checkedIn })
      .then((hints) => setGuestHints((ph) => ({ ...ph, [clientId]: hints })));
  }, []);

  // Load all guest baskets
  const loadAllBaskets = useCallback(async (slots: GuestSlot[]) => {
    for (const g of slots) {
      loadGuestBasket(g.client_id);
    }
  }, [loadGuestBasket]);

  // Save wizard state to sessionStorage before navigating away
  const saveWizardState = useCallback(() => {
    const state = {
      step,
      selectedTable,
      guestsCount,
      orderType,
      sessionTableId,
      guestSlots,
      guestBaskets,
      activeGuestIdx,
    };
    sessionStorage.setItem("newOrderWizard", JSON.stringify(state));
  }, [step, selectedTable, guestsCount, orderType, sessionTableId, guestSlots, guestBaskets, activeGuestIdx]);

  // Restore wizard state from sessionStorage on mount (skip if ?new=1)
  useEffect(() => {
    const isNew = new URLSearchParams(window.location.search).get("new") === "1";
    if (isNew) {
      sessionStorage.removeItem("newOrderWizard");
      return;
    }
    const saved = sessionStorage.getItem("newOrderWizard");
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.step) setStep(state.step);
        if (state.selectedTable) setSelectedTable(state.selectedTable);
        if (state.guestsCount) setGuestsCount(state.guestsCount);
        if (state.orderType) setOrderType(state.orderType);
        if (state.sessionTableId !== undefined) setSessionTableId(state.sessionTableId);
        if (state.guestSlots) setGuestSlots(state.guestSlots);
        if (state.guestBaskets) setGuestBaskets(state.guestBaskets);
        if (state.activeGuestIdx !== undefined) setActiveGuestIdx(state.activeGuestIdx);
      } catch {
        // ignore
      }
      sessionStorage.removeItem("newOrderWizard");
    }
  }, []);

  // Handle return from scan page
  useEffect(() => {
    if (scanHandledRef.current) return;
    const scannedClientId = searchParams.get("scannedClientId");
    const scannedGuestIdx = searchParams.get("scannedGuestIdx");
    if (scannedClientId && step === "fill") {
      scanHandledRef.current = true;
      const idx = parseInt(scannedGuestIdx || "0", 10);
      const realClientId = parseInt(scannedClientId, 10);
      const profile = nextLoyaltyProfile();
      setGuestSlots((prev) => {
        const updated = [...prev];
        if (updated[idx]) {
          updated[idx] = {
            ...updated[idx],
            client_id: realClientId,
            linked: true,
            name: profile.name,
            allergies: profile.allergies,
            checkedIn: true,
          };
        }
        return updated;
      });
      setActiveGuestIdx(idx);
      loadGuestBasket(realClientId);
      window.history.replaceState({}, "", "/dashboard/new-order");
    }
  }, [searchParams, step, loadGuestBasket]);

  const setGuestHungerNO = (clientId: number, level: HungerLevel) => {
    setGuestSlots((prev) => {
      const updated = prev.map((g) => g.client_id !== clientId ? g : { ...g, hunger: level });
      const g = updated.find(g => g.client_id === clientId);
      fetchRealHints(clientId, { hunger: level, allergies: g?.allergies, checkedIn: g?.checkedIn })
        .then(hints => setGuestHints((prev) => ({ ...prev, [clientId]: hints })));
      return updated;
    });
  };

  // Load all baskets when entering fill step
  useEffect(() => {
    if (step === "fill" && guestSlots.length > 0) {
      loadAllBaskets(guestSlots);
    }
  }, [step]);

  // Load menu + stop list when entering fill step
  useEffect(() => {
    if (step === "fill") {
      setMenuLoading(true);
      Promise.all([
        getMenu().then((data) => setMenu(data.menu || [])),
        getStopList().then((data) => setStoppedIds(new Set(data.stopped_dish_ids || []))).catch(() => {}),
      ]).finally(() => setMenuLoading(false));
    }
  }, [step]);

  // Active table numbers (mine) for color coding
  const [myTableNumbers, setMyTableNumbers] = useState<Set<string>>(new Set());

  // Load tables on mount
  useEffect(() => {
    setTablesLoading(true);
    Promise.all([
      getIikoTables().then((data) => setTables(data.tables || [])),
      getActiveTables().then((data) => {
        const nums = new Set<string>((data.tables || []).map((t: {table_number: string}) => t.table_number));
        setMyTableNumbers(nums);
      }).catch(() => {}),
    ])
      .catch((e) => setTablesError(e.message))
      .finally(() => setTablesLoading(false));
  }, []);

  // Filter tables
  const filteredTables = tables.filter(
    (t) =>
      t.name.toLowerCase().includes(tableSearch.toLowerCase()) ||
      String(t.number).includes(tableSearch) ||
      t.section_name.toLowerCase().includes(tableSearch.toLowerCase())
  );

  // Group filtered tables by section
  const sections = filteredTables.reduce<Record<string, IikoTable[]>>((acc, t) => {
    const key = t.section_name || "Без секции";
    if (!acc[key]) acc[key] = [];
    acc[key].push(t);
    return acc;
  }, {});

  // Step 1 -> Step 2
  const handleTableSelect = (table: IikoTable) => {
    setSelectedTable(table);
    setStep("guests");
  };

  // Step 2 -> Step 3: create session
  const handleCreateSession = async () => {
    if (!selectedTable) return;
    setSessionLoading(true);
    try {
      const res = await createTableSession(
        selectedTable.id,
        String(selectedTable.number),
        guestsCount,
        orderType
      );
      setSessionTableId(res.table_id);
      const slots: GuestSlot[] = (res.guests || []).map(
        (g: { guest_id: number; client_id: number; name: string; slot_index: number }) => ({
          ...g,
          linked: false,
          dish_count: 0,
        })
      );
      setGuestSlots(slots);
      setActiveGuestIdx(0);
      setStep("fill");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      showToast("Ошибка создания сессии: " + msg, "err");
    } finally {
      setSessionLoading(false);
    }
  };

  // Send entire session
  const handleSendOrder = async () => {
    if (sessionTableId === null) return;
    setSending(true);
    try {
      const res = await sendSessionOrder(sessionTableId, orderComment || undefined);
      sessionStorage.removeItem("newOrderWizard");
      showToast(res.message || "Заказ отправлен!");
      router.push("/dashboard");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      showToast("Ошибка: " + msg, "err");
    } finally {
      setSending(false);
    }
  };

  // Refresh a single guest's basket and count
  const refreshGuest = async (clientId: number) => {
    try {
      const data = await getBasket(clientId);
      const items: BasketItem[] = data.basket || [];
      setGuestBaskets((prev) => ({ ...prev, [clientId]: items }));
      setGuestSlots((prev) =>
        prev.map((g) =>
          g.client_id === clientId
            ? { ...g, dish_count: items.reduce((s, i) => s + i.quantity, 0) }
            : g
        )
      );
      // Recompute hints; reset dismissed when basket changes
      setGuestDismissed((prev) => ({ ...prev, [clientId]: new Set() }));
      const slot = guestSlots.find(g => g.client_id === clientId);
      fetchRealHints(clientId, { hunger: slot?.hunger, allergies: slot?.allergies, checkedIn: slot?.checkedIn })
        .then(hints => setGuestHints((prev) => ({ ...prev, [clientId]: hints })));
    } catch {
      // ignore
    }
  };

  // Add dish to active guest
  const handleAddDish = async (dishId: number, modifiers?: ModifierSelection[]) => {
    const guest = guestSlots[activeGuestIdx];
    if (!guest) return;
    try {
      await modifyBasket(guest.client_id, dishId, 1, modifiers);
      setAddedIds((prev) => new Set(prev).add(dishId));
      setTimeout(() => {
        setAddedIds((prev) => {
          const n = new Set(prev);
          n.delete(dishId);
          return n;
        });
      }, 600);
      await refreshGuest(guest.client_id);
    } catch (e) {
      console.error(e);
      showToast("Ошибка добавления", "err");
    }
  };

  // Open modifiers or add directly
  const openModifiersOrAdd = useCallback(async (dish: Dish) => {
    if (stoppedIds.has(dish.id)) return;
    setLoadingModifiers(true);
    try {
      const data = await getDishModifiers(dish.id);
      const mods: ModifierGroup[] = data.modifiers || [];
      if (mods.length > 0) {
        setModifiersDish(dish);
        setModifierGroups(mods);
        const defaults: Record<string, number> = {};
        for (const group of mods) {
          for (const opt of group.options) {
            defaults[opt.id] = opt.default_amount || 0;
          }
        }
        setModSelections(defaults);
      } else {
        await handleAddDish(dish.id);
      }
    } catch {
      await handleAddDish(dish.id);
    } finally {
      setLoadingModifiers(false);
    }
  }, [stoppedIds, activeGuestIdx, guestSlots]);

  // Open modifiers modal for an existing basket item
  const openModifiersForExisting = async (clientId: number, item: BasketItem) => {
    setLoadingModifiers(true);
    try {
      const data = await getDishModifiers(item.dish_id);
      const mods: ModifierGroup[] = data.modifiers || [];
      if (mods.length === 0) { showToast("Нет модификаторов"); return; }
      setModifiersDish({ id: item.dish_id, name: item.dish_name, category: "", description: "", price: item.price, image: null });
      setModifierGroups(mods);
      setEditingModFor({ clientId, dishId: item.dish_id });
      // Pre-fill from existing modifiers
      const sel: Record<string, number> = {};
      for (const group of mods) {
        for (const opt of group.options) {
          const existing = item.modifiers?.find((m) => m.modifier_id === opt.id);
          sel[opt.id] = existing ? existing.amount : (opt.default_amount || 0);
        }
      }
      setModSelections(sel);
    } catch {
      showToast("Ошибка загрузки модификаторов", "err");
    } finally {
      setLoadingModifiers(false);
    }
  };

  const handleModifiersConfirm = async () => {
    if (!modifiersDish) return;
    const mods: ModifierSelection[] = [];
    for (const group of modifierGroups) {
      for (const opt of group.options) {
        const amount = modSelections[opt.id] || 0;
        if (amount > 0) {
          mods.push({ modifier_id: opt.id, name: opt.name, amount, group_id: group.group_id });
        }
      }
    }
    if (editingModFor) {
      // Editing existing item — delta=0, just update modifiers
      await modifyBasket(editingModFor.clientId, editingModFor.dishId, 0, mods.length > 0 ? mods : undefined);
      refreshGuest(editingModFor.clientId);
      setEditingModFor(null);
    } else {
      await handleAddDish(modifiersDish.id, mods.length > 0 ? mods : undefined);
    }
    setModifiersDish(null);
    setModifierGroups([]);
    setModSelections({});
  };

  const totalDishes = guestSlots.reduce((s, g) => {
    const items = guestBaskets[g.client_id] || [];
    return s + items.reduce((sum, i) => sum + i.quantity, 0);
  }, 0);

  const totalPrice = guestSlots.reduce((s, g) => {
    const items = guestBaskets[g.client_id] || [];
    return s + items.reduce((sum, i) => sum + Number(i.subtotal), 0);
  }, 0);

  const activeGuest = guestSlots[activeGuestIdx];
  const isStopped = (dishId: number) => stoppedIds.has(dishId);

  return (
    <div className="h-screen bg-app flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-surface border-b border-hair-soft sticky top-0 z-10">
        {step === "fill" ? (
          /* iiko-style fill header: back text + centered title + QR right */
          <div className="flex items-center px-4 py-3">
            <button
              onClick={() => { saveWizardState(); router.push("/dashboard"); }}
              className="flex items-center gap-1 text-blue-500 font-medium text-sm mr-2 flex-shrink-0"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Заказы
            </button>
            <div className="flex-1 text-center">
              <h1 className="text-base font-semibold text-ink leading-tight">Стол {selectedTable?.number}</h1>
              <p className="text-xs text-ink-muted">Гостей {guestSlots.length}</p>
            </div>
            <button
              onClick={() => { saveWizardState(); router.push(`/dashboard/scan?returnTo=/dashboard/new-order&guestIdx=${activeGuestIdx}`); }}
              className="flex-shrink-0 w-9 h-9 flex items-center justify-center text-blue-500 ml-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm14 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
              </svg>
            </button>
          </div>
        ) : (
          /* Table/guests steps header */
          <div className="flex items-center px-4 py-3">
            <button
              onClick={() => {
                if (step === "guests") {
                  sessionTableId !== null ? router.push("/dashboard") : setStep("table");
                } else {
                  router.push("/dashboard");
                }
              }}
              className="flex items-center gap-1 text-blue-500 font-medium text-sm mr-2 flex-shrink-0"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Заказы
            </button>
            <div className="flex-1 text-center">
              <h1 className="text-base font-semibold text-ink">
                {step === "table" ? "Выберите стол" : `Стол ${selectedTable?.number}`}
              </h1>
              {step === "guests" && selectedTable && (
                <p className="text-xs text-ink-muted">{selectedTable.section_name}</p>
              )}
            </div>
            <div className="w-16" />
          </div>
        )}
      </header>

      {/* ====== STEP 1: TABLE SELECTION ====== */}
      {step === "table" && (
        <TableStep
          tableSearch={tableSearch}
          onSearch={setTableSearch}
          tablesLoading={tablesLoading}
          tablesError={tablesError}
          sections={sections}
          myTableNumbers={myTableNumbers}
          onSelect={handleTableSelect}
        />
      )}

      {/* ====== STEP 2: GUESTS & ORDER TYPE ====== */}
      {step === "guests" && selectedTable && (
        <GuestsStep
          table={selectedTable}
          guestsCount={guestsCount}
          onCountChange={setGuestsCount}
          sessionLoading={sessionLoading}
          onCreate={(ot) => { setOrderType(ot); handleCreateSession(); }}
        />
      )}


      {/* ====== STEP 3: FILL — GUESTS + INLINE MENU ====== */}
      {step === "fill" && (
        <FillStep
          guestSlots={guestSlots}
          setGuestSlots={setGuestSlots}
          guestBaskets={guestBaskets}
          setGuestBaskets={setGuestBaskets}
          guestHints={guestHints}
          setGuestHints={setGuestHints}
          guestDismissed={guestDismissed}
          setGuestDismissed={setGuestDismissed}
          activeGuestIdx={activeGuestIdx}
          setActiveGuestIdx={setActiveGuestIdx}
          menu={menu}
          menuLoading={menuLoading}
          isStopped={isStopped}
          addedIds={addedIds}
          loadingModifiers={loadingModifiers}
          openModifiersOrAdd={openModifiersOrAdd}
          openModifiersForExisting={openModifiersForExisting}
          refreshGuest={refreshGuest}
          showToast={showToast}
          saveWizardState={saveWizardState}
          setGuestHungerNO={setGuestHungerNO}
          openRecs={openRecs}
          sessionTableId={sessionTableId}
          orderComment={orderComment}
          setOrderComment={setOrderComment}
          sending={sending}
          onSend={handleSendOrder}
          totalDishes={totalDishes}
          totalPrice={totalPrice}
          setEditingComment={setEditingComment}
          router={router}
        />
      )}

      {/* Modifiers Modal */}
      {modifiersDish && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-end justify-center" onClick={() => setModifiersDish(null)}>
          <div className="bg-surface w-full max-w-lg rounded-t-3xl p-5 max-h-[70vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
            <h2 className="text-lg font-bold text-ink mb-1">{modifiersDish.name}</h2>
            <p className="text-sm text-ink-muted mb-4">Выберите модификаторы</p>
            <div className="space-y-4">
              {modifierGroups.map((group) => (
                <div key={group.group_id}>
                  <h3 className="text-sm font-bold text-ink mb-2">
                    {group.group_name}
                    {group.required && <span className="text-red-500 ml-1">*</span>}
                  </h3>
                  <div className="space-y-2">
                    {group.options.map((opt) => {
                      const amount = modSelections[opt.id] || 0;
                      return (
                        <div key={opt.id} className="flex items-center justify-between bg-inset rounded-xl px-3 py-2">
                          <div>
                            <span className="text-sm font-medium text-ink">{opt.name}</span>
                            {opt.price ? <span className="text-xs text-ink-subtle ml-2">+{opt.price} ₽</span> : null}
                          </div>
                          <div className="flex items-center gap-2">
                            <button onClick={() => setModSelections((prev) => ({ ...prev, [opt.id]: Math.max(opt.min_amount, amount - 1) }))} className="w-7 h-7 rounded-lg bg-surface border border-hair flex items-center justify-center text-ink-muted active:scale-95">-</button>
                            <span className="w-5 text-center font-bold text-sm">{amount}</span>
                            <button onClick={() => setModSelections((prev) => ({ ...prev, [opt.id]: Math.min(opt.max_amount, amount + 1) }))} className="w-7 h-7 rounded-lg bg-blue-500 text-white flex items-center justify-center active:scale-95">+</button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={() => { setModifiersDish(null); setModifierGroups([]); }} className="flex-1 py-3 rounded-xl border border-hair text-ink-muted font-semibold hover:bg-inset transition">Отмена</button>
              <button onClick={handleModifiersConfirm} className="flex-1 py-3 rounded-xl bg-blue-500 text-white font-semibold active:scale-[0.98] transition shadow-md">{editingModFor ? "Сохранить" : "Добавить"}</button>
            </div>
          </div>
        </div>
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
                className="flex-1 py-3 rounded-xl bg-blue-500 text-white font-semibold active:scale-[0.98] transition shadow-md"
              >Сохранить</button>
            </div>
          </div>
        </div>
      )}

      {/* Recommendations popup */}
      {recsPopup && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40" onClick={() => setRecsPopup(null)}>
          <div
            className="bg-surface w-full max-w-md rounded-t-2xl p-5 pb-8 animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-ink flex items-center gap-2">
                Подсказки для {recsPopup.name}
              </h3>
              <CloseButton variant="plain" onClose={() => setRecsPopup(null)} />
            </div>
            {recsPopup.loading ? (
              <div className="flex items-center justify-center py-8 text-ink-subtle">
                <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Загрузка...
              </div>
            ) : recsPopup.items.length === 0 ? (
              <p className="text-sm text-ink-muted text-center py-6">Нет рекомендаций для этого гостя</p>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-ink-muted mb-3">Также может подойти:</p>
                {recsPopup.items.map((rec, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-inset rounded-xl px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ink truncate">‣ {rec.name}</p>
                      <p className="text-xs text-ink-subtle">{rec.category}</p>
                    </div>
                    <span className="text-sm font-bold text-ink ml-3 flex-shrink-0">{rec.price} ₽</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      <Toast toast={toast} />
    </div>
  );
}

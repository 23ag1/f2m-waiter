"use client";

import { Suspense, useEffect, useState, useMemo, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getMenu, modifyBasket, getDishDetail, getDishModifiers, getStopList } from "@/shared/api";
import type { ModifierSelection } from "@/shared/api";
import { categoryColor } from "@/shared/lib/category-color";

interface Dish {
  id: number;
  category: string;
  name: string;
  description: string;
  price: number;
  image: string | null;
}

interface Category {
  category_name: string;
  dishes: Dish[];
}

interface ModifierOption {
  id: string;
  name: string;
  min_amount: number;
  max_amount: number;
  default_amount: number;
  price?: number;
}

interface ModifierGroup {
  group_id: string;
  group_name: string;
  required: boolean;
  min_selected: number;
  max_selected: number;
  options: ModifierOption[];
}

function MenuContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const clientId = searchParams.get("clientId");
  const mode = searchParams.get("mode");
  const returnTo = searchParams.get("returnTo");

  const [menu, setMenu] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [selectedDish, setSelectedDish] = useState<any>(null);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());
  const [stoppedIds, setStoppedIds] = useState<Set<number>>(new Set());
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 1500);
  };

  // Modifiers modal state
  const [modifiersDish, setModifiersDish] = useState<Dish | null>(null);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [modSelections, setModSelections] = useState<Record<string, number>>({});
  const [loadingModifiers, setLoadingModifiers] = useState(false);

  useEffect(() => {
    getMenu()
      .then((data) => setMenu(data.menu || []))
      .catch(console.error)
      .finally(() => setLoading(false));

    // Load stop-list
    getStopList()
      .then((data) => setStoppedIds(new Set(data.stopped_dish_ids || [])))
      .catch(console.error);
  }, []);

  const filteredMenu = useMemo(() => {
    if (!search.trim()) return menu;
    const q = search.toLowerCase();
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
  }, [menu, search]);

  const openModifiersOrAdd = useCallback(async (dish: Dish) => {
    if (stoppedIds.has(dish.id)) return;
    if (!clientId) return;

    setLoadingModifiers(true);
    try {
      const data = await getDishModifiers(dish.id);
      const mods: ModifierGroup[] = data.modifiers || [];
      if (mods.length > 0) {
        // Has modifiers — show modal
        setModifiersDish(dish);
        setModifierGroups(mods);
        // Set defaults
        const defaults: Record<string, number> = {};
        for (const group of mods) {
          for (const opt of group.options) {
            defaults[opt.id] = opt.default_amount || 0;
          }
        }
        setModSelections(defaults);
      } else {
        // No modifiers — add directly
        await handleAdd(dish.id);
      }
    } catch {
      // Fallback: add without modifiers
      await handleAdd(dish.id);
    } finally {
      setLoadingModifiers(false);
    }
  }, [clientId, stoppedIds]);

  const handleAdd = async (dishId: number, modifiers?: ModifierSelection[]) => {
    if (!clientId) return;
    try {
      await modifyBasket(Number(clientId), dishId, 1, modifiers);
      setAddedIds((prev) => new Set(prev).add(dishId));
      setTimeout(() => {
        setAddedIds((prev) => {
          const n = new Set(prev);
          n.delete(dishId);
          return n;
        });
      }, 1500);
    } catch (e) {
      console.error(e);
      showToast("Ошибка добавления", "err");
    }
  };

  const handleModifiersConfirm = async () => {
    if (!modifiersDish || !clientId) return;
    const mods: ModifierSelection[] = [];
    for (const group of modifierGroups) {
      for (const opt of group.options) {
        const amount = modSelections[opt.id] || 0;
        if (amount > 0) {
          mods.push({ modifier_id: opt.id, name: opt.name, amount });
        }
      }
    }
    await handleAdd(modifiersDish.id, mods.length > 0 ? mods : undefined);
    setModifiersDish(null);
    setModifierGroups([]);
    setModSelections({});
  };

  const openDishDetail = async (dish: Dish) => {
    try {
      const detail = await getDishDetail(dish.id);
      setSelectedDish(detail);
    } catch {
      setSelectedDish(dish);
    }
  };

  const goBack = () => {
    if (returnTo) {
      router.push(returnTo);
    } else if (clientId && mode === "add") {
      router.push(`/dashboard/basket/${clientId}`);
    } else {
      router.back();
    }
  };

  const isStopped = (dishId: number) => stoppedIds.has(dishId);

  return (
    <div className="min-h-screen bg-app flex flex-col">
      {/* Header */}
      <header className="p-4 bg-surface shadow-sm flex items-center border-b border-hair-soft sticky top-0 z-20">
        <button onClick={goBack} className="text-ink-muted p-2 -ml-2 rounded-full hover:bg-inset">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
        </button>
        <h1 className="text-lg font-bold ml-2 text-ink">
          {mode === "add" ? "Добавить блюда" : "Каталог меню"}
        </h1>
      </header>

      {/* Search */}
      <div className="p-4 bg-surface border-b border-hair-soft sticky top-[64px] z-10">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-ink-subtle" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Найти блюдо..."
            className="w-full pl-10 pr-4 py-3 bg-inset border border-hair rounded-xl text-sm font-medium text-ink placeholder-gray-400 focus:outline-none focus:border-black transition"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle hover:text-ink">
              x
            </button>
          )}
        </div>
      </div>

      {/* Menu */}
      <main className="flex-1 p-4 max-w-lg mx-auto w-full space-y-4 mt-2">
        {loading ? (
          <div className="text-center py-10 text-ink-muted">Загрузка меню...</div>
        ) : filteredMenu.length === 0 ? (
          <div className="text-center py-10 text-ink-muted">
            {search ? "Ничего не найдено" : "Меню пусто"}
          </div>
        ) : !search && !activeCategory ? (
          /* ====== CATEGORY GRID — coloured tiles (iiko-style) ====== */
          <div className="grid grid-cols-2 gap-3">
            {filteredMenu.map((cat, i) => {
              const c = categoryColor(cat.category_name);
              return (
                <button
                  key={i}
                  onClick={() => setActiveCategory(cat.category_name)}
                  className={`${c.bg} ${c.border} border rounded-2xl px-4 py-5 text-left transition active:scale-[0.98] flex flex-col justify-between min-h-24`}
                >
                  <h3 className="font-bold text-gray-900 text-base leading-tight">{cat.category_name}</h3>
                  <p className="text-xs text-gray-500 mt-2">{cat.dishes.length} блюд</p>
                </button>
              );
            })}
          </div>
        ) : (
          /* ====== DISH LIST (filtered by category or search) ====== */
          <>
            {activeCategory && !search && (
              <button
                onClick={() => setActiveCategory(null)}
                className="flex items-center gap-2 text-sm text-ink-muted hover:text-ink transition mb-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Все категории
              </button>
            )}
            {(activeCategory ? filteredMenu.filter(c => c.category_name === activeCategory) : filteredMenu).map((cat, i) => (
              <section key={i} className="space-y-3">
                <h2 className="text-lg font-bold text-ink border-b pb-2">{cat.category_name}</h2>
                <div className="grid gap-3">
                  {cat.dishes.map((dish) => {
                    const stopped = isStopped(dish.id);
                    return (
                      <div
                        key={dish.id}
                        className={`bg-surface p-3 rounded-2xl shadow-sm border border-hair-soft flex gap-3 items-center transition ${
                          stopped ? "opacity-50 pointer-events-none" : "cursor-pointer active:scale-[0.98]"
                        }`}
                        onClick={() => !stopped && openDishDetail(dish)}
                      >
                        {dish.image ? (
                          <div className="w-16 h-16 rounded-xl bg-inset flex-shrink-0 overflow-hidden relative">
                            <img src={`data:image/png;base64,${dish.image}`} alt={dish.name} className="w-full h-full object-cover" />
                            {stopped && (
                              <div className="absolute inset-0 bg-surface/70 flex items-center justify-center">
                                <span className="text-xs font-bold text-red-500 bg-red-50 px-2 py-1 rounded">СТОП</span>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="w-14 h-14 rounded-xl bg-orange-100 flex-shrink-0 flex items-center justify-center text-orange-500 relative">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                            {stopped && (
                              <div className="absolute inset-0 bg-surface/70 rounded-xl flex items-center justify-center">
                                <span className="text-xs font-bold text-red-500">СТОП</span>
                              </div>
                            )}
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <h3 className={`font-semibold leading-tight truncate text-sm ${stopped ? "text-ink-subtle line-through" : "text-ink"}`}>{dish.name}</h3>
                          <div className={`mt-1 font-bold text-sm ${stopped ? "text-ink-subtle" : "text-ink"}`}>{dish.price} ₽</div>
                        </div>

                        {mode === "add" && clientId && !stopped && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openModifiersOrAdd(dish);
                            }}
                            disabled={loadingModifiers}
                            className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg transition shadow-sm
                              ${addedIds.has(dish.id) ? "bg-green-500 text-white" : "bg-black text-white active:scale-90"}`}
                          >
                            {addedIds.has(dish.id) ? "✓" : "+"}
                          </button>
                        )}

                        {stopped && mode === "add" && (
                          <span className="flex-shrink-0 text-xs font-bold text-red-500 bg-red-50 px-3 py-2 rounded-xl">
                            СТОП
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </>
        )}
      </main>

      {/* Dish Detail Modal */}
      {selectedDish && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-end justify-center" onClick={() => setSelectedDish(null)}>
          <div className="bg-surface w-full max-w-lg rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />

            {selectedDish.image ? (
              <div className="w-full h-56 rounded-2xl bg-inset overflow-hidden mb-4">
                <img src={`data:image/png;base64,${selectedDish.image}`} alt={selectedDish.name} className="w-full h-full object-cover" />
              </div>
            ) : (
              <div className="w-full h-32 rounded-2xl bg-orange-50 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-orange-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
              </div>
            )}

            <h2 className="text-2xl font-bold text-ink mb-2">{selectedDish.name}</h2>
            <p className="text-sm text-ink-muted font-medium mb-3">{selectedDish.category}</p>

            {selectedDish.description && (
              <p className="text-ink-muted mb-3">{selectedDish.description}</p>
            )}
            {selectedDish.weight && (
              <p className="text-sm text-ink-subtle mb-1">Вес: {selectedDish.weight}</p>
            )}
            {selectedDish.ingredients && (
              <p className="text-sm text-ink-subtle mb-4">Состав: {selectedDish.ingredients}</p>
            )}

            <div className="flex items-center justify-between mt-4">
              <span className="text-2xl font-bold text-ink">{selectedDish.price} ₽</span>
              {mode === "add" && clientId && selectedDish.id && !isStopped(selectedDish.id) && (
                <button
                  onClick={() => {
                    openModifiersOrAdd(selectedDish);
                    setSelectedDish(null);
                  }}
                  className="bg-black text-white px-6 py-3 rounded-xl font-semibold active:scale-95 transition shadow-md"
                >
                  + Добавить
                </button>
              )}
              <button
                onClick={() => setSelectedDish(null)}
                className="text-ink-muted px-4 py-3 rounded-xl font-medium hover:bg-inset transition"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modifiers Modal */}
      {modifiersDish && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-end justify-center" onClick={() => setModifiersDish(null)}>
          <div className="bg-surface w-full max-w-lg rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
            <h2 className="text-xl font-bold text-ink mb-1">{modifiersDish.name}</h2>
            <p className="text-sm text-ink-muted mb-4">Выберите модификаторы</p>

            <div className="space-y-5">
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
                            <button
                              onClick={() =>
                                setModSelections((prev) => ({
                                  ...prev,
                                  [opt.id]: Math.max(opt.min_amount, amount - 1),
                                }))
                              }
                              className="w-7 h-7 rounded-lg bg-surface border border-hair flex items-center justify-center text-ink-muted active:scale-95"
                            >
                              -
                            </button>
                            <span className="w-5 text-center font-bold text-sm">{amount}</span>
                            <button
                              onClick={() =>
                                setModSelections((prev) => ({
                                  ...prev,
                                  [opt.id]: Math.min(opt.max_amount, amount + 1),
                                }))
                              }
                              className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center active:scale-95"
                            >
                              +
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setModifiersDish(null);
                  setModifierGroups([]);
                }}
                className="flex-1 py-3 rounded-xl border border-hair text-ink-muted font-semibold hover:bg-inset transition"
              >
                Отмена
              </button>
              <button
                onClick={handleModifiersConfirm}
                className="flex-1 py-3 rounded-xl bg-black text-white font-semibold active:scale-[0.98] transition shadow-md"
              >
                Добавить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className={`fixed top-6 left-1/2 -translate-x-1/2 z-[60] px-5 py-3 rounded-2xl shadow-lg text-sm font-semibold animate-fade-in ${
          toast.type === "ok" ? "bg-green-500 text-white" : "bg-red-500 text-white"
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

export function MenuView() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-app flex items-center justify-center text-ink-muted">Загрузка...</div>}>
      <MenuContent />
    </Suspense>
  );
}

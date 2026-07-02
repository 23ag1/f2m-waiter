"use client";

import { categoryColor } from "@/shared/lib/category-color";
import type { Category, Dish } from "@/entities/menu";

// Collapsible inline menu for the order card: coloured category grid → dish list.
export function MenuPanel({
  collapsed,
  onToggle,
  loading,
  categories,
  search,
  activeCategory,
  onCategory,
  isStopped,
  onAdd,
  adding,
  addedIds,
}: {
  collapsed: boolean;
  onToggle: () => void;
  loading: boolean;
  categories: Category[];
  search: string;
  activeCategory: string | null;
  onCategory: (name: string | null) => void;
  isStopped: (dishId: number) => boolean;
  onAdd: (dish: Dish) => void;
  adding: boolean;
  addedIds: Set<number>;
}) {
  return (
    <div className="shrink-0 bg-surface border-t-2 border-hair shadow-[0_-2px_8px_rgba(0,0,0,0.06)]">
      {/* Gray handle — always visible, acts as toggle */}
      <button onClick={onToggle} className="w-full flex flex-col items-center py-1 active:bg-inset transition">
        <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-6 text-ink-subtle transition-transform ${collapsed ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {!collapsed && (
        <div className="overflow-y-auto max-h-[60vh]">
          <div className="p-3 pb-4">
            {loading ? (
              <div className="text-center py-8 text-ink-subtle text-sm">Загрузка меню...</div>
            ) : categories.length === 0 ? (
              <div className="text-center py-8 text-ink-subtle text-sm">{search ? "Ничего не найдено" : "Меню пусто"}</div>
            ) : !search && !activeCategory ? (
              /* Category grid — coloured tiles (iiko-style) */
              <div className="grid grid-cols-2 gap-3">
                {categories.map((cat, i) => {
                  const c = categoryColor(cat.category_name);
                  return (
                    <button
                      key={i}
                      onClick={() => onCategory(cat.category_name)}
                      className={`${c.bg} ${c.border} border rounded-2xl px-4 py-5 text-left transition active:scale-[0.97] flex flex-col justify-between min-h-24`}
                    >
                      <h3 className="font-bold text-gray-900 text-base leading-tight">{cat.category_name}</h3>
                      <p className="text-xs text-gray-500 mt-2">{cat.dishes.length} блюд</p>
                    </button>
                  );
                })}
              </div>
            ) : (
              /* Dish list */
              <>
                {activeCategory && !search && (
                  <button onClick={() => onCategory(null)} className="flex items-center gap-1 text-sm text-ink-muted hover:text-ink transition mb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    Все категории
                  </button>
                )}
                {(activeCategory ? categories.filter((c) => c.category_name === activeCategory) : categories).map((cat, i) => (
                  <div key={i} className="mb-4">
                    <h2 className="text-base font-bold text-ink mb-2 px-1">{cat.category_name}</h2>
                    <div className="space-y-2">
                      {cat.dishes.map((dish) => {
                        const stopped = isStopped(dish.id);
                        return (
                          <div
                            key={dish.id}
                            className={`bg-surface px-3 py-3 rounded-xl border border-hair-soft flex items-center gap-3 transition ${stopped ? "opacity-40" : "active:scale-[0.98]"}`}
                          >
                            <div className="flex-1 min-w-0">
                              <p className={`text-base font-medium truncate ${stopped ? "text-ink-subtle line-through" : "text-ink"}`}>{dish.name}</p>
                              <p className={`text-sm ${stopped ? "text-ink-subtle" : "text-ink-muted"}`}>{dish.price} ₽</p>
                            </div>
                            {!stopped ? (
                              <button
                                onClick={() => onAdd(dish)}
                                disabled={adding}
                                className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm transition shadow-sm ${addedIds.has(dish.id) ? "bg-green-500 text-white" : "bg-black text-white active:scale-90"}`}
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
  );
}

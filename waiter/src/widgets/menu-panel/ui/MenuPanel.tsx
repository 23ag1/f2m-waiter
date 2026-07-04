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
              /* Category grid — compact equal tiles with a coloured left stripe (iiko-style) */
              <div className="grid grid-cols-3 gap-2">
                {categories.map((cat, i) => {
                  const c = categoryColor(cat.category_name);
                  return (
                    <button
                      key={i}
                      onClick={() => onCategory(cat.category_name)}
                      className="relative h-16 rounded-xl bg-inset border border-hair overflow-hidden flex items-center justify-center px-2 text-center active:scale-[0.97] transition"
                    >
                      <span className={`absolute left-0 inset-y-0 w-1.5 ${c.bar}`} />
                      <h3 className="text-xs font-bold text-ink leading-tight line-clamp-3">{cat.category_name}</h3>
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
                {(activeCategory ? categories.filter((c) => c.category_name === activeCategory) : categories).map((cat, i) => {
                  const cc = categoryColor(cat.category_name);
                  return (
                    <div key={i} className="mb-4">
                      <h2 className="text-base font-bold text-ink mb-2 px-1">{cat.category_name}</h2>
                      <div className="grid grid-cols-3 gap-2">
                        {cat.dishes.map((dish) => {
                          const stopped = isStopped(dish.id);
                          const added = addedIds.has(dish.id);
                          return (
                            <button
                              key={dish.id}
                              onClick={() => { if (!stopped) onAdd(dish); }}
                              disabled={adding || stopped}
                              className={`relative h-20 rounded-xl bg-surface border border-hair-soft overflow-hidden flex flex-col items-center justify-center px-2 pb-1.5 text-center transition ${stopped ? "opacity-40" : "active:scale-[0.97]"}`}
                            >
                              <p className={`text-xs font-semibold leading-tight line-clamp-2 ${stopped ? "text-ink-subtle line-through" : "text-ink"}`}>{dish.name}</p>
                              <p className="text-[11px] text-ink-muted mt-0.5">{dish.price} ₽</p>
                              <span className={`absolute bottom-0 inset-x-0 h-1 ${cc.bar}`} />
                              {stopped && <span className="absolute top-1 right-1 text-[9px] font-bold text-red-500 bg-red-50 px-1 rounded">СТОП</span>}
                              {added && <span className="absolute inset-0 bg-green-500/15 flex items-center justify-center text-green-600 text-xl font-bold">✓</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

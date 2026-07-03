"use client";

import { useState } from "react";
import { Toast } from "@/shared/ui/Toast";
import { useToast } from "@/shared/lib/use-toast";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { RecommendationCard } from "@/entities/recommendation";
import { BackButton } from "@/shared/ui/BackButton";
import { Stepper } from "@/shared/ui/Stepper";
import { useSendOrder } from "@/features/send-order";
import { useGuestBasket } from "../model/use-guest-basket";

// Single-client basket (QR-scan / menu-add flow, no table) — the original iiko-lite layout.
export function SingleGuestBasketView() {
  const router = useRouter();
  const { clientId } = useParams();
  const searchParams = useSearchParams();
  const tableParam = searchParams.get("table") || "";
  const cid = Number(clientId);

  const { toast, showToast } = useToast();

  const gb = useGuestBasket(cid, showToast);
  const [tableNum, setTableNum] = useState(tableParam);

  const { send, print } = useSendOrder({
    tableId: null,
    clientId: cid,
    tableNum: tableNum || tableParam,
    showToast,
    onDone: () => router.push("/dashboard"),
  });

  if (gb.loading) {
    return <div className="min-h-screen bg-app flex items-center justify-center text-ink-subtle">Загрузка...</div>;
  }

  const visibleHints = gb.hints.filter((h) => !gb.dismissedHintIds.has(h.id));

  return (
    <div className="min-h-screen bg-app flex flex-col pb-56">
      <header className="p-4 bg-surface shadow-sm flex items-center justify-between border-b border-hair-soft sticky top-0 z-10">
        <div className="flex items-center">
          <BackButton variant="inline" onClick={() => router.push("/dashboard")} />
          <div className="ml-2">
            <h1 className="text-lg font-bold text-ink leading-tight">Корзина Гостя</h1>
            <p className="text-xs text-ink-muted">
              {gb.hunger && <span className={`font-medium ${gb.hunger === "высокий" ? "text-red-500" : "text-blue-500"}`}>{gb.hunger === "высокий" ? "🔥 Сытный" : "🍃 Лёгкий"}</span>}
            </p>
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 max-w-lg mx-auto w-full space-y-4">
        {gb.basket.length === 0 ? (
          <div className="text-center py-10 bg-surface rounded-2xl border border-hair-soft mt-10 shadow-sm">
            <p className="text-ink-muted">Корзина пуста</p>
            <button
              onClick={() => router.push(`/dashboard/menu?clientId=${cid}&mode=add`)}
              className="mt-4 bg-black text-white px-6 py-3 rounded-xl font-semibold active:scale-95 transition"
            >
              + Добавить блюда
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {gb.basket.map((item) => (
                <div key={item.dish_id} className="bg-surface px-3 py-2 rounded-xl shadow-sm border border-hair-soft flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-base font-semibold text-ink leading-tight truncate">{item.dish_name}</p>
                    {item.modifiers && item.modifiers.length > 0 && (
                      <p className="text-xs text-orange-600 truncate">{item.modifiers.map((m) => m.name).join(", ")}</p>
                    )}
                    {item.comment && <p className="text-xs text-blue-500 truncate">{item.comment}</p>}
                    <p className="text-sm text-ink-subtle">{item.price} ₽ × {item.quantity}</p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <Stepper value={item.quantity} size="lg" onDec={() => gb.modify(item.dish_id, -1)} onInc={() => gb.modify(item.dish_id, 1)} />
                    <button onClick={() => gb.remove(item.dish_id)} className="w-7 h-7 rounded-lg flex items-center justify-center text-red-300 hover:text-red-500 transition ml-1">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Hint strip: horizontal scroll, color-coded by category */}
            {visibleHints.length > 0 && (
              <div className="overflow-x-auto -mx-1 px-1 pb-2 scrollbar-hide">
                <div className="flex gap-2 w-max">
                  {visibleHints.map((hint) => (
                    <RecommendationCard
                      key={hint.id}
                      hint={hint}
                      onAdd={() => gb.addHintLocally(hint)}
                      onDismiss={() => gb.dismissHint(hint.id)}
                    />
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => router.push(`/dashboard/menu?clientId=${cid}&mode=add`)}
              className="w-full py-3 rounded-xl border-2 border-dashed border-hair text-ink-muted font-medium hover:border-black hover:text-ink transition active:scale-[0.98]"
            >
              + Добавить ещё блюда
            </button>

            {gb.recommendations.length > 0 && (
              <div className="mt-2">
                <h3 className="text-sm font-bold text-ink-muted uppercase tracking-wider mb-3">
                  Также может подойти
                </h3>
                <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-hide">
                  {gb.recommendations.map((rec, idx) => (
                    <div key={idx} className="flex-shrink-0 w-36 bg-surface rounded-2xl border border-hair-soft shadow-sm overflow-hidden">
                      {rec.image ? (
                        <div className="w-full h-24 bg-inset">
                          <img src={`data:image/png;base64,${rec.image}`} alt={rec.name} className="w-full h-full object-cover" />
                        </div>
                      ) : (
                        <div className="w-full h-20 bg-orange-50 flex items-center justify-center">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-orange-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                        </div>
                      )}
                      <div className="p-3">
                        <p className="text-xs font-semibold text-ink leading-tight line-clamp-2">{rec.name}</p>
                        <p className="text-xs text-ink-subtle mt-1">{rec.category}</p>
                        <div className="flex items-center justify-between mt-2">
                          <span className="font-bold text-ink text-sm">{rec.price} ₽</span>
                          <button
                            onClick={() => gb.addRecommendation(rec)}
                            className="w-7 h-7 rounded-lg bg-black text-white text-sm flex items-center justify-center active:scale-90 transition"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* Bottom Sticky Action Bar */}
      {gb.basket.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-surface border-t border-hair p-4 pb-8 shadow-[0_-4px_20px_rgba(0,0,0,0.05)]">
          <div className="max-w-lg mx-auto">
            <div className="flex justify-between items-center mb-4 px-2">
              <span className="text-ink-muted font-medium text-sm uppercase">Итого</span>
              <span className="text-2xl font-bold text-ink">{gb.totalCost} ₽</span>
            </div>
            <div className="flex flex-col space-y-3">
              {!tableParam && (
                <input
                  type="text"
                  value={tableNum}
                  onChange={(e) => setTableNum(e.target.value)}
                  placeholder="Стол №"
                  className="w-full bg-inset border border-hair rounded-xl px-4 py-3 font-medium text-ink placeholder-gray-400 focus:outline-none focus:border-black"
                />
              )}
              <div className="flex space-x-3">
                <button onClick={() => send("")} className="flex-1 bg-surface border border-black text-ink rounded-xl py-3 font-semibold shadow-sm active:bg-inset transition transform active:scale-[0.98]">
                  Отправить
                </button>
                <button onClick={print} className="flex-1 bg-black text-white rounded-xl py-3 font-semibold shadow-md active:bg-gray-800 transition transform active:scale-[0.98]">
                  Пречек
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      <Toast toast={toast} />
    </div>
  );
}

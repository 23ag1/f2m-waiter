"use client";

import { categoryColor } from "@/shared/lib/category-color";

// Standalone showcase page: several recommendation-card concepts for the team to
// review/approve. Goal from feedback: not intrusive, compact (3 fit on screen),
// and the WHY (reason) readable at a glance. Colours kept.

type ReasonKey = "wine" | "hit" | "special" | "profile" | "promo";

const REASONS: Record<ReasonKey, { icon: string; label: string; bar: string; chip: string; text: string; dot: string }> = {
  wine:    { icon: "🍷", label: "К красному вину", bar: "bg-rose-500",   chip: "bg-rose-100 text-rose-700 border-rose-200",       text: "text-rose-600",   dot: "bg-rose-500" },
  hit:     { icon: "⭐", label: "Хит продаж",       bar: "bg-amber-500",  chip: "bg-amber-100 text-amber-700 border-amber-200",    text: "text-amber-600",  dot: "bg-amber-500" },
  special: { icon: "🔥", label: "Блюдо дня",        bar: "bg-orange-500", chip: "bg-orange-100 text-orange-700 border-orange-200", text: "text-orange-600", dot: "bg-orange-500" },
  profile: { icon: "👤", label: "По профилю гостя", bar: "bg-blue-500",   chip: "bg-blue-100 text-blue-700 border-blue-200",       text: "text-blue-600",   dot: "bg-blue-500" },
  promo:   { icon: "📢", label: "Продвигаем",       bar: "bg-violet-500", chip: "bg-violet-100 text-violet-700 border-violet-200", text: "text-violet-600", dot: "bg-violet-500" },
};

interface Item { name: string; price: number; cat: string; r: ReasonKey }

const ITEMS: Item[] = [
  { name: "Рибай стейк", price: 2490, cat: "Горячее", r: "wine" },
  { name: "Сырная тарелка", price: 890, cat: "Закуски", r: "hit" },
  { name: "Борщ со сметаной", price: 490, cat: "Супы", r: "special" },
];

const AddBtn = ({ small }: { small?: boolean }) => (
  <button className={`${small ? "w-6 h-6 rounded-md text-sm" : "w-7 h-7 rounded-lg text-base"} bg-black text-white font-bold flex items-center justify-center flex-shrink-0`}>+</button>
);

// ── Variant 1: coloured reason bar on top ───────────────────────────────
function V1() {
  return (
    <div className="grid grid-cols-3 gap-2">
      {ITEMS.map((it, i) => {
        const r = REASONS[it.r];
        return (
          <div key={i} className="rounded-xl overflow-hidden border border-hair bg-surface flex flex-col">
            <div className={`${r.bar} px-2 py-1 flex items-center gap-1`}>
              <span className="text-xs leading-none">{r.icon}</span>
              <span className="text-[11px] font-bold text-white truncate">{r.label}</span>
            </div>
            <div className="p-2 flex-1 flex flex-col">
              <p className="text-xs font-semibold text-ink leading-tight line-clamp-2 min-h-[2rem]">{it.name}</p>
              <div className="flex items-center justify-between mt-auto pt-1">
                <span className="text-xs font-bold text-ink">{it.price} ₽</span>
                <AddBtn small />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Variant 2: full-width scannable rows ────────────────────────────────
function V2() {
  return (
    <div className="rounded-xl border border-hair bg-surface divide-y divide-hair-soft overflow-hidden">
      {ITEMS.map((it, i) => {
        const r = REASONS[it.r];
        return (
          <div key={i} className="flex items-center gap-3 px-3 py-2.5">
            <span className={`w-8 h-8 rounded-lg border flex items-center justify-center text-sm flex-shrink-0 ${r.chip}`}>{r.icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-ink truncate">{it.name}</p>
              <p className={`text-xs font-semibold ${r.text} truncate`}>{r.label}</p>
            </div>
            <span className="text-sm font-bold text-ink flex-shrink-0">{it.price} ₽</span>
            <AddBtn />
          </div>
        );
      })}
    </div>
  );
}

// ── Variant 3: category pastel + reason chip ────────────────────────────
function V3() {
  return (
    <div className="grid grid-cols-3 gap-2">
      {ITEMS.map((it, i) => {
        const c = categoryColor(it.cat);
        const r = REASONS[it.r];
        return (
          <div key={i} className={`rounded-xl ${c.bg} border ${c.border} p-2 flex flex-col gap-1.5`}>
            <p className="text-xs font-semibold text-gray-800 leading-tight line-clamp-2 min-h-[2rem]">{it.name}</p>
            <span className={`inline-flex items-center gap-1 self-start text-[10px] font-bold px-1.5 py-0.5 rounded-full border ${r.chip}`}>
              {r.icon} {r.label}
            </span>
            <div className="flex items-center justify-between mt-auto pt-0.5">
              <span className="text-xs font-bold text-gray-800">{it.price} ₽</span>
              <AddBtn small />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Variant 4: reason-led mini card (icon hero) ─────────────────────────
function V4() {
  return (
    <div className="grid grid-cols-3 gap-2">
      {ITEMS.map((it, i) => {
        const r = REASONS[it.r];
        return (
          <div key={i} className="rounded-xl border border-hair bg-surface p-2 flex flex-col items-center text-center gap-1">
            <span className={`w-9 h-9 rounded-full border flex items-center justify-center text-lg ${r.chip}`}>{r.icon}</span>
            <p className="text-xs font-semibold text-ink leading-tight line-clamp-2 min-h-[2rem]">{it.name}</p>
            <span className={`text-[10px] font-bold ${r.text} leading-tight`}>{r.label}</span>
            <div className="flex items-center justify-between w-full mt-auto pt-1">
              <span className="text-xs font-bold text-ink">{it.price} ₽</span>
              <AddBtn small />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Section({ n, title, idea, children }: { n: number; title: string; idea: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <div className="flex items-baseline gap-2 mb-1">
        <span className="w-6 h-6 rounded-full bg-blue-500 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">{n}</span>
        <h2 className="text-base font-bold text-ink">{title}</h2>
      </div>
      <p className="text-xs text-ink-muted mb-3 pl-8">{idea}</p>
      <div className="bg-app rounded-2xl border border-hair-soft p-3">{children}</div>
    </section>
  );
}

export function RecConceptsView() {
  return (
    <div className="min-h-screen bg-surface">
      <header className="px-4 pt-10 pb-4 border-b border-hair-soft">
        <h1 className="text-2xl font-extrabold text-ink tracking-tight">Карточки рекомендаций</h1>
        <p className="text-sm text-ink-muted mt-1">Концепты для согласования</p>
        <div className="mt-3 rounded-xl bg-inset p-3 text-xs text-ink-muted leading-relaxed">
          Задача: подсказки не навязчивые, компактные (3 карточки влезают на экран),
          и <span className="font-semibold text-ink">причина рекомендации читается с первого взгляда</span> —
          к чему подойдёт / блюдо дня / хит / по профилю. Цвета сохраняем.
        </div>
      </header>

      <main className="px-4 py-5">
        <Section n={1} title="Причина-плашка сверху" idea="Цветная полоска с причиной над названием — глаз цепляется за «зачем» первым.">
          <V1 />
        </Section>
        <Section n={2} title="Строки-список" idea="Полноширинные строки: иконка причины · блюдо · причина · цена. Максимально сканируемо, влезает больше трёх.">
          <V2 />
        </Section>
        <Section n={3} title="Пастель + чип причины" idea="Наш текущий пастель по категории, но причина вынесена в заметный чип.">
          <V3 />
        </Section>
        <Section n={4} title="Мини с иконкой-причиной" idea="Крупная иконка причины как якорь внимания, всё компактно.">
          <V4 />
        </Section>

        <p className="text-xs text-ink-subtle text-center py-4">
          Легенда причин: 🍷 сочетание · ⭐ хит · 🔥 блюдо дня · 👤 по профилю · 📢 продвигаем (менеджер)
        </p>
      </main>
    </div>
  );
}

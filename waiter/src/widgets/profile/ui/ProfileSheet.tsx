"use client";

import { useEffect, useState } from "react";
import { LogOut, ChevronRight } from "lucide-react";
import { Sheet } from "@/shared/ui/Sheet";
import { BackButton } from "@/shared/ui/BackButton";
import { Avatar } from "@/shared/ui/Avatar";
import { SegmentedControl } from "@/shared/ui/SegmentedControl";
import { ThemeSwitch } from "@/shared/ui/ThemeSwitch";
import { useTheme } from "@/shared/lib/theme";
import { RecSettingsScreen } from "@/widgets/rec-settings";
import { startTour, useTourPhase } from "@/features/onboarding";

// iiko-style waiter profile screen.
// NOTE: the backend exposes no sales/stats endpoints yet, so "Личные продажи",
// the chart and "Допродажи" use placeholder data (like the iiko demo, which
// shows 0,00 ₽ with sample bars). "Мой процент" is stored locally.

type Period = "day" | "week" | "month";

const MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const MONTHS_NOM = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];

const PERCENT_KEY = "waiter_percent";

// Placeholder chart data per period (label + relative value). Replace with a
// real backend endpoint when one exists.
const CHART: Record<Period, { label: string; value: number }[]> = {
  day: [
    { label: "12", value: 0 }, { label: "14", value: 0 }, { label: "16", value: 0 },
    { label: "18", value: 0 }, { label: "20", value: 0 }, { label: "22", value: 0 },
  ],
  week: [
    { label: "22", value: 40 }, { label: "23", value: 0 }, { label: "24", value: 90 },
    { label: "25", value: 12 }, { label: "26", value: 12 }, { label: "27", value: 48 },
    { label: "28", value: 0 },
  ],
  month: [
    { label: "1", value: 30 }, { label: "6", value: 60 }, { label: "11", value: 20 },
    { label: "16", value: 75 }, { label: "21", value: 45 }, { label: "26", value: 15 },
  ],
};

function fmtMoney(n: number): string {
  return n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function rangeLabel(period: Period): string {
  const now = new Date();
  if (period === "day") return `${now.getDate()} ${MONTHS_GEN[now.getMonth()]}`;
  if (period === "month") return MONTHS_NOM[now.getMonth()];
  const start = new Date(now);
  start.setDate(now.getDate() - 6);
  return `${start.getDate()} ${MONTHS_GEN[start.getMonth()]} — ${now.getDate()} ${MONTHS_GEN[now.getMonth()]}`;
}

export function ProfileSheet({
  open,
  onClose,
  onLogout,
  name = "Официант",
  initial = "W",
}: {
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  name?: string;
  initial?: string;
}) {
  const { mode, set: setTheme } = useTheme();
  const [period, setPeriod] = useState<Period>("week");
  const [percent, setPercent] = useState(10);
  const [editPercent, setEditPercent] = useState(false);
  const [draft, setDraft] = useState("10,0");
  const [showRecSettings, setShowRecSettings] = useState(false);
  const tourPhase = useTourPhase();
  const recOpen = showRecSettings || tourPhase === "recset";

  useEffect(() => {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(PERCENT_KEY) : null;
    if (raw) setPercent(parseFloat(raw) || 10);
  }, []);

  if (!open) return null;

  const total = 0; // no real sales data yet
  const cut = (total * percent) / 100;
  const bars = CHART[period];
  const maxValue = Math.max(1, ...bars.map((b) => b.value));

  const openEdit = () => {
    setDraft(percent.toFixed(1).replace(".", ","));
    setEditPercent(true);
  };

  const savePercent = () => {
    const v = Math.min(100, Math.max(0, parseFloat(draft.replace(",", ".")) || 0));
    setPercent(v);
    try { window.localStorage.setItem(PERCENT_KEY, String(v)); } catch { /* ignore */ }
    setEditPercent(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-inset overflow-y-auto">
      {/* Nav — back circle */}
      <div className="px-4 pt-12 pb-1">
        <BackButton onClick={onClose} />
      </div>

      {/* Avatar + name */}
      <div className="flex flex-col items-center pt-1 pb-5">
        <div className="mb-3">
          <Avatar initial={initial} size="lg" />
        </div>
        <p className="text-xl font-bold text-ink">{name}</p>
      </div>

      {/* Выйти */}
      <div className="px-4 mb-5">
        <button
          onClick={onLogout}
          className="w-full py-4 rounded-2xl bg-inset text-blue-500 text-sm font-semibold flex items-center justify-center gap-2 active:scale-[0.98] transition"
        >
          <LogOut className="h-5 w-5" />
          Выйти
        </button>
      </div>

      {/* Тема оформления */}
      <div className="px-4 mb-3">
        <div className="bg-surface rounded-2xl p-4 shadow-sm flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-bold text-ink">Тема оформления</p>
            <p className="text-xs text-ink-muted mt-1">{mode === "dark" ? "Тёмная" : "Светлая"}</p>
          </div>
          <ThemeSwitch dark={mode === "dark"} onChange={(d) => setTheme(d ? "dark" : "light")} />
        </div>
      </div>

      {/* Настройки рекомендаций */}
      <div className="px-4 mb-3">
        <button
          data-tour="profile-rec"
          onClick={() => setShowRecSettings(true)}
          className="w-full bg-surface rounded-2xl p-4 shadow-sm flex items-center gap-3 active:scale-[0.99] transition text-left"
        >
          <span className="text-lg leading-none">💡</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-ink">Настройки рекомендаций</p>
            <p className="text-xs text-ink-subtle mt-1">Порядок категорий и цвет шапок</p>
          </div>
          <ChevronRight className="h-4 w-4 text-ink-subtle" strokeWidth={2.5} />
        </button>
      </div>

      {/* Пройти обучение — replays the onboarding tour from the dashboard */}
      <div className="px-4 mb-3">
        <button
          onClick={() => { onClose(); startTour(); }}
          className="w-full bg-surface rounded-2xl p-4 shadow-sm flex items-center gap-3 active:scale-[0.99] transition text-left"
        >
          <span className="text-lg leading-none">🎓</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-ink">Пройти обучение</p>
            <p className="text-xs text-ink-subtle mt-1">Повторить знакомство с рекомендациями</p>
          </div>
          <ChevronRight className="h-4 w-4 text-ink-subtle" strokeWidth={2.5} />
        </button>
      </div>

      {/* Допродажи за сегодня */}
      <div className="px-4 mb-3">
        <div className="bg-surface rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <p className="text-sm font-bold text-ink">Допродажи за сегодня</p>
            <ChevronRight className="h-4 w-4 text-ink-subtle" strokeWidth={2.5} />
          </div>
          <p className="text-2xl font-extrabold text-ink">{fmtMoney(0)} ₽</p>
          <p className="text-xs text-ink-subtle mt-1">0 Блюд</p>
        </div>
      </div>

      {/* Личные продажи */}
      <div className="px-4 mb-3">
        <div className="bg-surface rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-bold text-ink">Личные продажи</p>
            <button onClick={openEdit} className="text-blue-500 font-semibold text-sm">
              Мой процент
            </button>
          </div>
          <p className="text-xs text-ink-muted">{rangeLabel(period)}</p>
          <p className="text-2xl font-extrabold text-ink mt-1">{fmtMoney(total)} ₽</p>
          <p className="text-xs text-ink-subtle mt-1">
            {fmtMoney(cut)} ₽ ({percent.toFixed(1).replace(".", ",")}%)
          </p>

          {/* Bar chart */}
          <div className="mt-3 flex items-end justify-between gap-2 h-24">
            {bars.map((b, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                <div
                  className="w-full bg-inset rounded-md min-h-1"
                  style={{ height: `${(b.value / maxValue) * 100}%` }}
                />
              </div>
            ))}
          </div>
          <div className="flex justify-between gap-2 mt-1">
            {bars.map((b, i) => (
              <span key={i} className="flex-1 text-center text-xs text-ink-subtle">{b.label}</span>
            ))}
          </div>

          {/* Period segmented control */}
          <SegmentedControl<Period>
            className="mt-3"
            options={[{ value: "day", label: "День" }, { value: "week", label: "Неделя" }, { value: "month", label: "Месяц" }]}
            value={period}
            onChange={setPeriod}
          />
        </div>
      </div>

      {/* Footer note */}
      <p className="px-5 pb-8 text-xs text-ink-subtle">
        Учитываются закрытые заказы, в которых вы назначены официантом
      </p>

      {/* Мой процент — top sheet so the input stays visible above the keyboard */}
      <Sheet open={editPercent} onClose={() => setEditPercent(false)} title="Мой процент">
        <input
          autoFocus
          inputMode="decimal"
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value.replace(/[^0-9.,]/g, "").replace(".", ","))}
          className="w-full bg-inset rounded-2xl px-4 py-4 text-lg font-semibold text-ink outline-none mb-4"
        />
        <button
          onClick={savePercent}
          className="w-full py-4 rounded-2xl bg-blue-500 text-white font-bold text-base active:scale-[0.98] transition"
        >
          Готово
        </button>
      </Sheet>

      {/* Настройки рекомендаций — full-screen */}
      <RecSettingsScreen open={recOpen} onClose={() => setShowRecSettings(false)} />
    </div>
  );
}

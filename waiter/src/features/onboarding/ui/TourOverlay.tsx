"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getActiveTables } from "@/shared/api";
import { TOUR_STEPS, useTour, nextStep, prevStep, finishTour } from "../model/onboarding";

// Renders the coach-mark for the current tour step: a dimmed backdrop with a
// cut-out around the anchored element, a tooltip with an arrow, step controls,
// and (for some steps) an animated affordance. Also drives the cross-screen
// navigation the tour needs (opening an order card for the "order" phase).
export function TourOverlay() {
  const { active, index } = useTour();
  const step = active ? TOUR_STEPS[index] : null;
  const router = useRouter();
  const pathname = usePathname();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const navigating = useRef(false);

  // Order phase needs an actual order card — jump to the first active table.
  useEffect(() => {
    if (!step || step.phase !== "order") { navigating.current = false; return; }
    if (pathname.startsWith("/dashboard/basket/")) return;
    if (navigating.current) return;
    navigating.current = true;
    getActiveTables()
      .then((data) => {
        const t = (data.tables || [])[0];
        if (!t) { finishTour(); return; }
        const clientId = t.guests?.[0]?.client_id ?? t.client_id;
        router.push(`/dashboard/basket/${clientId}?table=${t.table_number}&tableId=${t.id}`);
      })
      .catch(() => finishTour());
  }, [step, pathname, router]);

  // Keep the highlight glued to the anchor while overlays/scroll animate.
  useEffect(() => {
    if (!step) { setRect(null); return; }
    let raf = 0;
    let last = "";
    const tick = () => {
      const el = document.querySelector(`[data-tour="${step.anchor}"]`);
      if (el) {
        const r = el.getBoundingClientRect();
        const key = `${Math.round(r.top)}-${Math.round(r.left)}-${Math.round(r.width)}-${Math.round(r.height)}`;
        if (key !== last) { last = key; setRect(r); }
      } else if (last !== "none") {
        last = "none";
        setRect(null);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [step]);

  if (!step) return null;

  const vw = typeof window !== "undefined" ? window.innerWidth : 390;
  const vh = typeof window !== "undefined" ? window.innerHeight : 844;
  const pad = 8;
  const isLast = index === TOUR_STEPS.length - 1;

  // Tooltip geometry
  const TT_W = Math.min(300, vw - 24);
  const centerX = rect ? rect.left + rect.width / 2 : vw / 2;
  const ttLeft = Math.max(12, Math.min(vw - TT_W - 12, centerX - TT_W / 2));
  const arrowLeft = Math.max(20, Math.min(TT_W - 28, centerX - ttLeft));
  const below = !rect || step.placement === "bottom";
  const ttTop = rect ? (below ? rect.bottom + pad + 12 : rect.top - pad - 12) : vh / 2;

  const holeStyle = rect
    ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }
    : null;

  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true">
      {/* Dim backdrop with a cut-out around the anchor (4 rectangles) */}
      {holeStyle ? (
        <>
          <div className="absolute left-0 right-0 top-0 bg-black/60" style={{ height: Math.max(0, holeStyle.top) }} />
          <div className="absolute left-0 right-0 bg-black/60" style={{ top: holeStyle.top + holeStyle.height, bottom: 0 }} />
          <div className="absolute bg-black/60" style={{ top: holeStyle.top, left: 0, width: Math.max(0, holeStyle.left), height: holeStyle.height }} />
          <div className="absolute bg-black/60" style={{ top: holeStyle.top, left: holeStyle.left + holeStyle.width, right: 0, height: holeStyle.height }} />
          {/* highlight ring */}
          <div
            className="absolute rounded-2xl ring-2 ring-white/90 pointer-events-none"
            style={{ top: holeStyle.top, left: holeStyle.left, width: holeStyle.width, height: holeStyle.height }}
          />
          {step.demo && <DemoHint kind={step.demo} rect={rect!} />}
        </>
      ) : (
        <div className="absolute inset-0 bg-black/60" />
      )}

      {/* Tooltip */}
      <div
        className="absolute animate-panel-expand"
        style={{ left: ttLeft, top: ttTop, width: TT_W, transform: below ? undefined : "translateY(-100%)" }}
      >
        <div
          className={`absolute w-3 h-3 rotate-45 bg-surface ${below ? "-top-1.5" : "-bottom-1.5"}`}
          style={{ left: arrowLeft }}
        />
        <div className="relative bg-surface rounded-2xl shadow-xl p-4">
          <p className="text-[15px] font-semibold text-ink leading-snug">{step.text}</p>
          <div className="flex items-center justify-between mt-4">
            <button
              onClick={prevStep}
              disabled={index === 0}
              className={`text-sm font-semibold px-3 py-1.5 rounded-lg ${index === 0 ? "text-ink-subtle/40" : "text-ink-muted active:bg-inset"}`}
            >
              Назад
            </button>
            <div className="flex items-center gap-1.5">
              {TOUR_STEPS.map((_, i) => (
                <span key={i} className={`h-1.5 rounded-full transition-all ${i === index ? "w-4 bg-blue-500" : "w-1.5 bg-ink-subtle/40"}`} />
              ))}
            </div>
            <button
              onClick={nextStep}
              className="text-sm font-bold px-4 py-1.5 rounded-lg bg-blue-500 text-white active:scale-95 transition"
            >
              {isLast ? "Готово" : "Далее"}
            </button>
          </div>
        </div>
      </div>

      {/* Skip */}
      <button
        onClick={finishTour}
        className="absolute top-4 right-4 text-xs font-semibold text-white/80 bg-black/40 rounded-full px-3 py-1.5 active:scale-95"
      >
        Пропустить
      </button>
    </div>
  );
}

// Small animated affordance drawn over the anchor.
function DemoHint({ kind, rect }: { kind: "drag" | "tap" | "swipe"; rect: DOMRect }) {
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  if (kind === "tap") {
    return (
      <span
        className="absolute rounded-full ring-2 ring-white pointer-events-none animate-ping"
        style={{ top: cy - 22, left: cx - 22, width: 44, height: 44 }}
      />
    );
  }
  // drag = vertical, swipe = upward — both a bouncing arrow glyph
  return (
    <span
      className="absolute pointer-events-none text-white text-2xl"
      style={{ top: cy - 16, left: cx - 12, animation: "tour-bounce 0.9s ease-in-out infinite" }}
    >
      {kind === "swipe" ? "↑" : "↕"}
    </span>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getActiveTables } from "@/shared/api";
import { TOUR_STEPS, useTour, nextStep, prevStep, finishTour } from "../model/onboarding";

interface Hole { top: number; left: number; width: number; height: number; radius: number }

// Renders the coach-mark for the current tour step: a single box-shadow spotlight
// that hugs the anchor's real shape (round targets stay round — no square corners),
// a tooltip with an arrow, step controls, and light demo animations. Also drives
// the cross-screen navigation the tour needs (opening an order card).
export function TourOverlay() {
  const { active, index } = useTour();
  const step = active ? TOUR_STEPS[index] : null;
  const router = useRouter();
  const pathname = usePathname();
  const [hole, setHole] = useState<Hole | null>(null);
  const navigating = useRef(false);

  // Order phase needs a real order card — jump to the first active table.
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

  // Keep the highlight glued to the anchor (and match its border-radius) while
  // overlays / scroll animate.
  useEffect(() => {
    if (!step) { setHole(null); return; }
    let raf = 0;
    let last = "";
    const pad = 6;
    const tick = () => {
      const el = document.querySelector(`[data-tour="${step.anchor}"]`);
      if (el) {
        const r = el.getBoundingClientRect();
        const cr = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0;
        const circular = cr >= Math.min(r.width, r.height) / 2 - 1;
        const w = r.width + pad * 2;
        const h = r.height + pad * 2;
        const radius = circular ? Math.min(w, h) / 2 : Math.min(16, cr + pad);
        const key = `${Math.round(r.top)}-${Math.round(r.left)}-${Math.round(r.width)}-${Math.round(r.height)}`;
        if (key !== last) {
          last = key;
          setHole({ top: r.top - pad, left: r.left - pad, width: w, height: h, radius });
        }
      } else if (last !== "none") {
        last = "none";
        setHole(null);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [step]);

  if (!step) return null;

  const vw = typeof window !== "undefined" ? window.innerWidth : 390;
  const vh = typeof window !== "undefined" ? window.innerHeight : 844;
  const isLast = index === TOUR_STEPS.length - 1;

  // Tooltip geometry
  const TT_W = Math.min(300, vw - 24);
  const centerX = hole ? hole.left + hole.width / 2 : vw / 2;
  const ttLeft = Math.max(12, Math.min(vw - TT_W - 12, centerX - TT_W / 2));
  const arrowLeft = Math.max(20, Math.min(TT_W - 28, centerX - ttLeft));
  const below = !hole || step.placement === "bottom";
  const ttTop = hole ? (below ? hole.top + hole.height + 12 : hole.top - 12) : vh / 2;

  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true">
      {/* Tap catcher (blocks the page; controls sit above it) */}
      <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />

      {/* Spotlight — one element, dim + white ring via box-shadow, hugs the shape */}
      {hole ? (
        <div
          key={step.id}
          className="absolute pointer-events-none"
          style={{
            top: hole.top,
            left: hole.left,
            width: hole.width,
            height: hole.height,
            borderRadius: hole.radius,
            boxShadow: "0 0 0 3px rgba(255,255,255,0.9), 0 0 0 9999px rgba(0,0,0,0.62)",
            animation: step.demo === "drag"
              ? "tour-drag-bob 1.4s ease-in-out infinite"
              : "tour-pop 0.28s ease-out",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-black/60" />
      )}

      {/* Demo affordances */}
      {hole && step.demo === "swipe" && <SwipeHint hole={hole} />}
      {hole && step.demo === "tap" && (
        <span
          className="absolute pointer-events-none ring-2 ring-white/80 animate-ping"
          style={{ top: hole.top, left: hole.left, width: hole.width, height: hole.height, borderRadius: hole.radius }}
        />
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
                <span key={i} className={`h-1.5 rounded-full transition-all duration-300 ${i === index ? "w-4 bg-blue-500" : "w-1.5 bg-ink-subtle/40"}`} />
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
        className="absolute top-4 right-4 text-xs font-semibold text-white/80 bg-black/40 rounded-full px-3 py-1.5 active:scale-95 transition"
      >
        Пропустить
      </button>
    </div>
  );
}

// Clean upward "swipe" affordance: a stacked double chevron in a soft pill,
// floating up over the card centre, on loop.
function SwipeHint({ hole }: { hole: Hole }) {
  const cx = hole.left + hole.width / 2;
  const top = hole.top + hole.height / 2 - 16;
  return (
    <div
      className="absolute pointer-events-none flex items-center justify-center rounded-full bg-blue-500/90 shadow-lg"
      style={{ left: cx - 16, top, width: 32, height: 32, animation: "tour-swipe-up 1.15s ease-in-out infinite" }}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 13l6-6 6 6" />
        <path d="M6 19l6-6 6 6" opacity="0.5" />
      </svg>
    </div>
  );
}

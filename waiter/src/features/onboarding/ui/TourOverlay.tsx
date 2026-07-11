"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getActiveTables } from "@/shared/api";
import { LoaderCircle, ChevronRight, ChevronsUpDown } from "lucide-react";
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
  const [altActive, setAltActive] = useState(false); // alt anchor (e.g. opened picker) matched
  const [orderWaited, setOrderWaited] = useState(false); // safety valve for the order-phase veil
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

  // The order-phase veil hides the page until the hint strip is on screen; the
  // timer is a safety valve so an order with no recommendations can't veil forever.
  useEffect(() => {
    if (step?.phase !== "order") { setOrderWaited(false); return; }
    const t = window.setTimeout(() => setOrderWaited(true), 5000);
    return () => window.clearTimeout(t);
  }, [step?.phase]);

  // Keep the highlight glued to the anchor (and match its border-radius) while
  // overlays / scroll animate.
  useEffect(() => {
    setHole(null); // drop the previous step's rect so stale anchors don't linger
    if (!step) return;
    let raf = 0;
    let last = "";
    const pad = 6;
    const tick = () => {
      // Prefer the alt anchor when it exists (e.g. the colour picker once opened),
      // so the spotlight + tooltip move to what the waiter is actually using.
      const altEl = step.anchorAlt ? document.querySelector(`[data-tour="${step.anchorAlt}"]`) : null;
      const el = altEl || document.querySelector(`[data-tour="${step.anchor}"]`);
      setAltActive(!!altEl);
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

  // On demo steps (drag / pick colour / swipe) the whole screen stays interactive
  // so the waiter can actually try the gesture during the tour. Other steps block
  // the page and advance via the buttons.
  const interactive = !!step.demo;

  // While hopping to the order card (recset → order) the dashboard/loading page
  // would flash through — cover the whole transition with an opaque veil until
  // the hint strip is actually on screen (or the safety timer fires).
  if (step.phase === "order" && (!pathname.startsWith("/dashboard/basket/") || (!hole && !orderWaited))) {
    return (
      <div className="fixed inset-0 z-[100] bg-app flex flex-col items-center justify-center gap-3" role="dialog" aria-modal="true">
        <LoaderCircle className="h-7 w-7 text-blue-500 animate-spin" strokeWidth={3} />
        <p className="text-sm font-semibold text-ink-muted">Открываем заказ…</p>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] pointer-events-none" role="dialog" aria-modal="true">
      {/* Tap catcher — blocks the page except on interactive demo steps */}
      {!interactive && <div className="absolute inset-0 pointer-events-auto" onClick={(e) => e.stopPropagation()} />}

      {/* Spotlight — one element that hugs the anchor's shape: crisp thin ring,
          a soft halo, and the surrounding dim, all via layered box-shadows. */}
      {hole ? (
        <div
          key={`spot-${step.id}`}
          className="absolute pointer-events-none"
          style={{
            top: hole.top,
            left: hole.left,
            width: hole.width,
            height: hole.height,
            borderRadius: hole.radius,
            boxShadow:
              "0 0 0 1.5px rgba(255,255,255,0.85), 0 0 22px 2px rgba(255,255,255,0.18), 0 0 0 9999px rgba(6,10,18,0.68)",
            animation: step.demo === "drag"
              ? "tour-drag-bob 1.4s ease-in-out infinite"
              : "tour-pop 0.3s cubic-bezier(0.2,0.9,0.25,1)",
          }}
        />
      ) : (
        <div className="absolute inset-0" style={{ background: "rgba(6,10,18,0.68)" }} />
      )}

      {/* Demo affordances */}
      {hole && step.demo === "swipe" && <SwipeHint hole={hole} />}
      {hole && step.demo === "tap" && !altActive && (
        <span
          className="absolute pointer-events-none ring-2 ring-white/80 animate-ping"
          style={{ top: hole.top, left: hole.left, width: hole.width, height: hole.height, borderRadius: hole.radius }}
        />
      )}

      {/* Tooltip */}
      <div
        key={`tip-${step.id}`}
        className="absolute animate-tour-tip pointer-events-auto"
        style={{ left: ttLeft, top: ttTop, width: TT_W, transform: below ? undefined : "translateY(-100%)" }}
      >
        <div
          className={`absolute w-3 h-3 rotate-45 rounded-sm bg-surface ${below ? "-top-1" : "-bottom-1"}`}
          style={{ left: arrowLeft }}
        />
        <div className="relative bg-surface rounded-[20px] p-4 shadow-[0_12px_40px_-8px_rgba(0,0,0,0.45)] ring-1 ring-black/5">
          {/* eyebrow: step counter + slim progress */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold tracking-wide uppercase text-ink-subtle">
              Обучение · {index + 1}/{TOUR_STEPS.length}
            </span>
            <button onClick={finishTour} className="text-xs font-semibold text-ink-subtle active:text-ink-muted transition">
              Пропустить
            </button>
          </div>
          <div className="h-1 rounded-full bg-inset overflow-hidden mb-3">
            <div className="h-full rounded-full bg-blue-500 transition-[width] duration-300 ease-out" style={{ width: `${((index + 1) / TOUR_STEPS.length) * 100}%` }} />
          </div>

          <p className="text-sm font-semibold text-ink leading-snug">{step.text}</p>

          <div className="flex items-center justify-between mt-4">
            {index > 0 ? (
              <button onClick={prevStep} className="text-sm font-semibold text-ink-muted px-2 py-2 -ml-2 rounded-lg active:bg-inset transition">
                Назад
              </button>
            ) : <span />}
            <button
              onClick={nextStep}
              className="inline-flex items-center gap-1 text-sm font-bold pl-5 pr-4 py-2 rounded-full bg-blue-500 text-white shadow-sm active:scale-[0.97] transition"
            >
              {isLast ? "Готово" : "Далее"}
              {!isLast && (
                <ChevronRight className="h-4 w-4" strokeWidth={2.5} />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// "Swipe both ways" affordance: a soft pill with up + down chevrons that rocks
// vertically over the card centre, on loop.
function SwipeHint({ hole }: { hole: Hole }) {
  const cx = hole.left + hole.width / 2;
  const top = hole.top + hole.height / 2 - 16;
  return (
    <div
      className="absolute pointer-events-none flex items-center justify-center rounded-full bg-blue-500/90 shadow-lg"
      style={{ left: cx - 16, top, width: 32, height: 32, animation: "tour-swipe-both 1.5s ease-in-out infinite" }}
    >
      <ChevronsUpDown width={20} height={20} className="text-white" strokeWidth={2.4} />
    </div>
  );
}

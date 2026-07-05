"use client";

import { useEffect, useRef, useState } from "react";
import { RecommendationCard } from "./RecommendationCard";
import { recColorFor } from "../model/rec-settings";
import type { HintDish } from "../model/hints-mock";

const THRESHOLD = 34; // px of vertical travel to trigger a replace

// One recommendation "slot": a fixed box that shows a single card and lets the
// waiter swipe it UP or DOWN to swap in another dish of the same category. The
// swap is a vertical carousel contained inside the slot — the replacement slides
// in from the opposite edge (swipe up → next enters from below; swipe down →
// from above). Neighbouring slots never move.
export function RecoSlot({
  initial,
  onAdd,
  onReplace,
  dataTour,
}: {
  initial: HintDish;
  onAdd: (h: HintDish) => void;
  onReplace: (current: HintDish, dir: "up" | "down") => Promise<HintDish | null>;
  dataTour?: string;
}) {
  const [card, setCard] = useState(initial);
  const [drag, setDrag] = useState(0);
  const [dragging, setDragging] = useState(false);
  // `from` = the finger offset at release, so the outgoing card CONTINUES from
  // where it was let go instead of snapping back to 0 first (that was the jerk).
  const [anim, setAnim] = useState<{ to: HintDish; dir: "up" | "down"; from: number; run: boolean } | null>(null);

  const el = useRef<HTMLDivElement>(null);
  const st = useRef<{ x: number; y: number; lock: 0 | 1 | 2 } | null>(null);
  const dragRef = useRef(0);
  const busy = useRef(false);
  // Commit-the-swap callback; fired by the incoming card's transitionend (the
  // fixed timeout used before could beat the transition → end-of-slide snap).
  const settleRef = useRef<(() => void) | null>(null);

  // Re-seed when the parent hands a fresh recommendation set.
  useEffect(() => { setCard(initial); setAnim(null); setDrag(0); busy.current = false; }, [initial.id]);

  useEffect(() => {
    const node = el.current;
    if (!node) return;

    const onStart = (e: TouchEvent) => {
      if (busy.current) return;
      const t = e.touches[0];
      st.current = { x: t.clientX, y: t.clientY, lock: 0 };
    };
    const onMove = (e: TouchEvent) => {
      if (!st.current || busy.current) return;
      const t = e.touches[0];
      const dx = t.clientX - st.current.x;
      const dy = t.clientY - st.current.y;
      if (st.current.lock === 0) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        st.current.lock = Math.abs(dy) > Math.abs(dx) ? 1 : 2;
        if (st.current.lock === 1) setDragging(true);
      }
      if (st.current.lock !== 1) return; // horizontal → let the strip scroll
      e.preventDefault();
      dragRef.current = dy * 0.55; // rubber-band
      setDrag(dragRef.current);
    };
    const onEnd = () => {
      const wasV = st.current?.lock === 1;
      st.current = null;
      setDragging(false);
      if (!wasV || busy.current) { setDrag(0); dragRef.current = 0; return; }
      const d = dragRef.current;
      if (Math.abs(d) < THRESHOLD) { setDrag(0); dragRef.current = 0; return; }
      const dir: "up" | "down" = d < 0 ? "up" : "down";
      busy.current = true;
      // HOLD the card at the release offset while the replacement resolves —
      // resetting to 0 here caused a visible snap-back before the slide-out.
      onReplace(card, dir).then((next) => {
        if (!next) { busy.current = false; setDrag(0); dragRef.current = 0; return; }
        setAnim({ to: next, dir, from: dragRef.current, run: false });
        setDrag(0);
        dragRef.current = 0;
        requestAnimationFrame(() => requestAnimationFrame(() => setAnim((a) => (a ? { ...a, run: true } : a))));
        // Swap state exactly when the slide transition finishes (transitionend),
        // never mid-flight — the timeout is only a fallback (hidden tab etc.).
        let fired = false;
        const finish = () => {
          if (fired) return;
          fired = true;
          settleRef.current = null;
          setCard(next);
          setAnim(null);
          busy.current = false;
        };
        settleRef.current = finish;
        window.setTimeout(finish, 650);
      });
    };

    node.addEventListener("touchstart", onStart, { passive: true });
    node.addEventListener("touchmove", onMove, { passive: false });
    node.addEventListener("touchend", onEnd, { passive: true });
    node.addEventListener("touchcancel", onEnd, { passive: true });
    return () => {
      node.removeEventListener("touchstart", onStart);
      node.removeEventListener("touchmove", onMove);
      node.removeEventListener("touchend", onEnd);
      node.removeEventListener("touchcancel", onEnd);
    };
  }, [card, onReplace]);

  return (
    <div ref={el} data-tour={dataTour} className="relative w-28 h-[92px] flex-shrink-0 overflow-hidden rounded-xl touch-pan-x">
      {/* Both states render a KEYED ARRAY at the same level, so the div showing a
          given dish is the SAME DOM node across the whole lifecycle. Before this,
          the branch switch (fragment ↔ single div) remounted the visible card at
          commit — the DOM churn read as a jump right after the card settled. Now
          the settled incoming div is reused verbatim (transform 0 → 0, no churn). */}
      {(anim
        ? [
            // outgoing card: continues from the finger's release offset
            <div
              key={`c-${card.id}`}
              className="absolute inset-0"
              style={{ transform: anim.run ? `translateY(${anim.dir === "up" ? "-100%" : "100%"})` : `translateY(${anim.from}px)`, transition: anim.run ? "transform 360ms cubic-bezier(0.22,1,0.36,1)" : "none" }}
            >
              <RecommendationCard hint={card} color={recColorFor(card.category)} onAdd={() => onAdd(card)} />
            </div>,
            // incoming card: slides in from the opposite edge; the swap commits
            // on ITS transitionend so the settle is exact
            <div
              key={`c-${anim.to.id}`}
              className="absolute inset-0"
              style={{ transform: anim.run ? "translateY(0)" : `translateY(${anim.dir === "up" ? "100%" : "-100%"})`, transition: anim.run ? "transform 360ms cubic-bezier(0.22,1,0.36,1)" : "none" }}
              onTransitionEnd={(e) => { if (e.target === e.currentTarget && e.propertyName === "transform") settleRef.current?.(); }}
            >
              <RecommendationCard hint={anim.to} color={recColorFor(anim.to.category)} onAdd={() => onAdd(anim.to)} />
            </div>,
          ]
        : [
            <div
              key={`c-${card.id}`}
              className="absolute inset-0"
              style={{ transform: `translateY(${drag}px)`, transition: dragging ? "none" : "transform 260ms cubic-bezier(0.22,1,0.36,1)" }}
            >
              <RecommendationCard hint={card} color={recColorFor(card.category)} onAdd={() => onAdd(card)} />
            </div>,
          ])}
    </div>
  );
}

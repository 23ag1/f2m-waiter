"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

// Swipe a recommendation card UP to dismiss it. Axis-locked so it never fights
// the horizontal scroll of the strip: a mostly-vertical drag is ours (we
// preventDefault), a horizontal drag is left to the scroll container.
// On release past the threshold the card flies up + fades, then onDismiss fires.

const THRESHOLD = 44; // px up to trigger dismiss
const FLY = 160;      // px it travels while leaving

export function SwipeUpDismiss({
  children,
  onDismiss,
  className = "",
}: {
  children: ReactNode;
  onDismiss: () => void;
  className?: string;
}) {
  const [dy, setDy] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [dragging, setDragging] = useState(false);
  const el = useRef<HTMLDivElement>(null);
  const st = useRef<{ x: number; y: number; lock: 0 | 1 | 2 } | null>(null);
  const dyRef = useRef(0);

  useEffect(() => {
    const node = el.current;
    if (!node) return;

    const onStart = (e: TouchEvent) => {
      if (leaving) return;
      const t = e.touches[0];
      st.current = { x: t.clientX, y: t.clientY, lock: 0 };
    };
    const onMove = (e: TouchEvent) => {
      if (!st.current || leaving) return;
      const t = e.touches[0];
      const dx = t.clientX - st.current.x;
      const dyy = t.clientY - st.current.y;
      if (st.current.lock === 0) {
        if (Math.abs(dx) < 8 && Math.abs(dyy) < 8) return;
        st.current.lock = Math.abs(dyy) > Math.abs(dx) ? 1 : 2;
        if (st.current.lock === 1) setDragging(true);
      }
      if (st.current.lock !== 1) return; // horizontal → let the strip scroll
      e.preventDefault();
      // only upward travel; tiny rubber-band downward
      const next = dyy < 0 ? dyy : dyy * 0.25;
      dyRef.current = Math.max(-FLY, next);
      setDy(dyRef.current);
    };
    const onEnd = () => {
      const wasV = st.current?.lock === 1;
      st.current = null;
      setDragging(false);
      if (!wasV) return;
      if (dyRef.current < -THRESHOLD) {
        setLeaving(true);
        setDy(-FLY);
        window.setTimeout(onDismiss, 180);
      } else {
        dyRef.current = 0;
        setDy(0);
      }
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
  }, [leaving, onDismiss]);

  const progress = Math.min(1, Math.abs(dy) / FLY);
  return (
    <div
      ref={el}
      className={`touch-pan-x ${className} ${dragging ? "" : "transition-all duration-200 ease-out"}`}
      style={{ transform: `translateY(${dy}px)`, opacity: leaving ? 0 : 1 - progress * 0.7 }}
    >
      {children}
    </div>
  );
}

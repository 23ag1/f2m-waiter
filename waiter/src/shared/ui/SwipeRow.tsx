"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

// Smooth swipe-to-reveal row (iiko-style). Keeps all drag state LOCAL so the
// parent list never re-renders during a drag — that was the source of the jank.
// Uses a non-passive touchmove listener so we can preventDefault the vertical
// scroll while dragging horizontally, and a CSS transition only for the snap.

export interface SwipeAction {
  label: string;
  icon: ReactNode;
  bg: string; // e.g. "bg-red-500"
  onClick: () => void;
}

const ACTION_W = 116; // px reserved per action pill

export function SwipeRow({
  children,
  leftActions = [], // revealed on swipe RIGHT
  rightActions = [], // revealed on swipe LEFT
}: {
  children: ReactNode;
  leftActions?: SwipeAction[];
  rightActions?: SwipeAction[];
}) {
  const rightW = rightActions.length * ACTION_W;
  const leftW = leftActions.length * ACTION_W;

  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const offsetRef = useRef(0);
  const el = useRef<HTMLDivElement>(null);
  const st = useRef<{ x: number; y: number; base: number; lock: 0 | 1 | 2 } | null>(null);

  const move = (to: number) => { offsetRef.current = to; setOffset(to); };
  const close = () => move(0);

  useEffect(() => {
    const node = el.current;
    if (!node) return;

    const onStart = (e: TouchEvent) => {
      const t = e.touches[0];
      st.current = { x: t.clientX, y: t.clientY, base: offsetRef.current, lock: 0 };
    };
    const onMove = (e: TouchEvent) => {
      if (!st.current) return;
      const t = e.touches[0];
      const dx = t.clientX - st.current.x;
      const dy = t.clientY - st.current.y;
      if (st.current.lock === 0) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        st.current.lock = Math.abs(dx) > Math.abs(dy) ? 1 : 2;
        if (st.current.lock === 1) setDragging(true);
      }
      if (st.current.lock !== 1) return;
      e.preventDefault(); // stop vertical scroll while swiping
      let next = st.current.base + dx;
      // small rubber-band beyond the open width
      next = Math.max(-rightW - 24, Math.min(leftW + 24, next));
      offsetRef.current = next;
      setOffset(next);
    };
    const onEnd = () => {
      const wasH = st.current?.lock === 1;
      st.current = null;
      setDragging(false);
      if (!wasH) return;
      const o = offsetRef.current;
      if (o < -rightW * 0.35 && rightW > 0) move(-rightW);
      else if (o > leftW * 0.35 && leftW > 0) move(leftW);
      else move(0);
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
  }, [rightW, leftW]);

  const pill = (a: SwipeAction, i: number) => (
    <button
      key={i}
      onClick={() => { a.onClick(); close(); }}
      className={`flex-1 my-1 rounded-full ${a.bg} text-white flex items-center justify-center gap-2 text-sm font-semibold active:brightness-95`}
    >
      {a.icon}
      <span>{a.label}</span>
    </button>
  );

  return (
    <div className="relative overflow-hidden">
      {rightActions.length > 0 && (
        <div className="absolute inset-y-0 right-0 flex items-stretch gap-2 pr-2" style={{ width: rightW }}>
          {rightActions.map(pill)}
        </div>
      )}
      {leftActions.length > 0 && (
        <div className="absolute inset-y-0 left-0 flex items-stretch gap-2 pl-2" style={{ width: leftW }}>
          {leftActions.map(pill)}
        </div>
      )}
      <div
        ref={el}
        className={`relative bg-surface touch-pan-y ${dragging ? "" : "transition-transform duration-200 ease-out"}`}
        style={{ transform: `translateX(${offset}px)` }}
        onClickCapture={(e) => {
          // If open, a tap on the content just closes it (doesn't trigger the row).
          if (offsetRef.current !== 0) { e.stopPropagation(); e.preventDefault(); close(); }
        }}
      >
        {children}
      </div>
    </div>
  );
}

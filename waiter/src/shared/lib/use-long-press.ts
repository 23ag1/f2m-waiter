"use client";

import { useRef } from "react";

const LONG_PRESS_MS = 420;
const MOVE_TOLERANCE = 10;

// Reusable long-press (touch-hold / right-click) handler. On the web a hold also
// triggers native text selection + the callout menu, so ALWAYS pair the returned
// handlers with `select-none [-webkit-touch-callout:none]` on the element.
// `fired` is used by the caller's onClick to swallow the click that follows a hold.
export function useLongPress(onLongPress?: () => void) {
  const timer = useRef<number | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const fired = useRef(false);

  const clear = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } };

  const onTouchStart = (e: React.TouchEvent) => {
    if (!onLongPress) return;
    fired.current = false;
    const t = e.touches[0];
    start.current = { x: t.clientX, y: t.clientY };
    timer.current = window.setTimeout(() => {
      fired.current = true;
      try { navigator.vibrate?.(10); } catch { /* ignore */ }
      onLongPress();
    }, LONG_PRESS_MS);
  };
  const onTouchMove = (e: React.TouchEvent) => {
    if (!start.current) return;
    const t = e.touches[0];
    if (Math.abs(t.clientX - start.current.x) > MOVE_TOLERANCE || Math.abs(t.clientY - start.current.y) > MOVE_TOLERANCE) clear();
  };
  const onContextMenu = (e: React.MouseEvent) => {
    if (!onLongPress) return;
    e.preventDefault();
    fired.current = true;
    onLongPress();
  };
  // Call from the element's onClick to cancel the click synthesised after a hold.
  const consumeClick = (e: React.MouseEvent | React.SyntheticEvent) => {
    if (fired.current) { e.preventDefault(); e.stopPropagation(); fired.current = false; return true; }
    return false;
  };

  return {
    handlers: { onTouchStart, onTouchMove, onTouchEnd: clear, onTouchCancel: clear, onContextMenu },
    consumeClick,
  };
}

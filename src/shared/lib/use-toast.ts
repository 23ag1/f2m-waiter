"use client";

import { useCallback, useRef, useState } from "react";
import type { ToastState } from "@/shared/ui/Toast";

// Shared toast hook — one implementation instead of the copy in every screen.
export function useToast(duration = 1500) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<number | null>(null);
  const showToast = useCallback((msg: string, type: "ok" | "err" = "ok") => {
    if (timer.current) clearTimeout(timer.current);
    setToast({ msg, type });
    timer.current = window.setTimeout(() => setToast(null), duration);
  }, [duration]);
  return { toast, showToast };
}

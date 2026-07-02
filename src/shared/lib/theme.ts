"use client";

import { useEffect, useState } from "react";

export type ThemeMode = "light" | "dark";

const KEY = "waiter_theme";

export function currentTheme(): ThemeMode {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle("dark", mode === "dark");
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* ignore */
  }
}

// Reads the theme already applied by the no-flash script (see app/layout.tsx),
// then lets the UI switch it. Persists to localStorage.
export function useTheme(): { mode: ThemeMode; set: (m: ThemeMode) => void; toggle: () => void } {
  const [mode, setMode] = useState<ThemeMode>("light");
  useEffect(() => {
    setMode(currentTheme());
  }, []);
  const set = (m: ThemeMode) => {
    applyTheme(m);
    setMode(m);
  };
  const toggle = () => set(mode === "dark" ? "light" : "dark");
  return { mode, set, toggle };
}

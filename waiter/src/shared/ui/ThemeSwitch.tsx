"use client";

import { Moon, Sun } from "lucide-react";

// iOS-style toggle in the app's own palette: neutral track off, blue-500 track on
// (same accent as the primary buttons / active guest row). The thumb carries the
// icon of the current theme.
export function ThemeSwitch({ dark, onChange }: { dark: boolean; onChange: (dark: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label="Тёмная тема"
      onClick={() => onChange(!dark)}
      // 56×32 track, 4px inset, 24px thumb → 24px of travel. An inset ring rather
      // than a border, so the light theme keeps the exact same box as the dark one.
      className={`relative flex items-center w-14 h-8 rounded-full p-1 shrink-0 transition-colors duration-200 active:scale-95 ${
        dark ? "bg-blue-500" : "bg-inset inset-ring-1 inset-ring-hair"
      }`}
    >
      <span
        className={`relative block w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-200 ease-out ${
          dark ? "translate-x-6" : "translate-x-0"
        }`}
      >
        <Sun className={`absolute inset-0 m-auto h-4 w-4 text-ink-subtle transition-opacity duration-150 ${dark ? "opacity-0" : "opacity-100"}`} />
        <Moon className={`absolute inset-0 m-auto h-4 w-4 text-blue-500 transition-opacity duration-150 ${dark ? "opacity-100" : "opacity-0"}`} />
      </span>
    </button>
  );
}

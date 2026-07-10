"use client";

import { X as XIcon } from "lucide-react";

// Close (✕) button. `circle` = grey circle (sheet headers); `plain` = bare icon
// (modal/popup headers).
export function CloseButton({
  onClose,
  variant = "circle",
}: {
  onClose: () => void;
  variant?: "circle" | "plain";
}) {
  const X = <XIcon className={variant === "circle" ? "h-4 w-4" : "h-5 w-5"} strokeWidth={2.5} />;
  if (variant === "plain") {
    return (
      <button onClick={onClose} aria-label="Закрыть" className="text-ink-subtle hover:text-ink-muted active:scale-95 transition">
        {X}
      </button>
    );
  }
  return (
    <button
      onClick={onClose}
      aria-label="Закрыть"
      className="w-8 h-8 rounded-full bg-inset flex items-center justify-center text-ink-muted active:scale-95 transition-transform"
    >
      {X}
    </button>
  );
}

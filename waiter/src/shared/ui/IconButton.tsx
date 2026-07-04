"use client";

import { type ReactNode } from "react";

// Square icon button used in headers/pills — one size source instead of copies.
const SIZES = { md: "w-10 h-10", tall: "w-9 h-11" } as const;

export function IconButton({
  onClick,
  children,
  size = "md",
  ariaLabel,
  className = "",
}: {
  onClick?: () => void;
  children: ReactNode;
  size?: keyof typeof SIZES;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel}
      className={`${SIZES[size]} flex items-center justify-center text-ink active:scale-90 transition ${className}`}
    >
      {children}
    </button>
  );
}

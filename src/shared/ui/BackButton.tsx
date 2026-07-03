"use client";

// One back button for the whole app — consistent size everywhere.
//  variant="floating" (default): white circle with shadow, for screens over a
//    grey background (order card, profile).
//  variant="inline": plain icon (optionally with a label), for white header bars
//    (menu, single-guest basket) and the iiko "‹ Заказы" text back.
export function BackButton({
  onClick,
  variant = "floating",
  label,
  tone = "default",
}: {
  onClick: () => void;
  variant?: "floating" | "inline";
  label?: string;
  tone?: "default" | "accent";
}) {
  const Chevron = (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
    </svg>
  );

  if (variant === "inline") {
    return (
      <button
        onClick={onClick}
        aria-label={label ?? "Назад"}
        className={`flex items-center gap-1 p-2 -ml-2 rounded-full active:scale-95 transition ${
          tone === "accent" ? "text-blue-500 font-medium" : "text-ink-muted hover:bg-inset"
        }`}
      >
        {Chevron}
        {label && <span className="text-sm">{label}</span>}
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      aria-label="Назад"
      className="w-10 h-10 rounded-full bg-surface shadow-sm flex items-center justify-center text-ink active:scale-95 transition-transform flex-shrink-0"
    >
      {Chevron}
    </button>
  );
}

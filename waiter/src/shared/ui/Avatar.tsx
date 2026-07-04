"use client";

// Circular initial avatar — consistent across profile, orders header, waiter list.
const SIZES = {
  sm: "w-10 h-10 text-sm",
  md: "w-11 h-11 text-base",
  lg: "w-20 h-20 text-3xl",
} as const;

export function Avatar({
  initial,
  size = "md",
  onClick,
}: {
  initial: string;
  size?: keyof typeof SIZES;
  onClick?: () => void;
}) {
  const cls = `${SIZES[size]} rounded-full bg-gray-400 flex items-center justify-center text-white font-bold flex-shrink-0`;
  if (onClick) {
    return (
      <button onClick={onClick} className={`${cls} active:scale-95 transition-transform`}>
        {initial}
      </button>
    );
  }
  return <div className={cls}>{initial}</div>;
}

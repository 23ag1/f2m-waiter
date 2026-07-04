"use client";

// −/value/+ quantity stepper. Was hand-rolled in several baskets.
// `accent` keeps each screen's existing look (card = black, new-order = blue).
const BTN = { sm: "w-6 h-6 rounded-md", md: "w-7 h-7 rounded-lg", lg: "w-8 h-8 rounded-lg" } as const;
const VAL = { sm: "w-4 text-xs", md: "w-5 text-sm", lg: "w-5 text-base" } as const;

export function Stepper({
  value,
  onDec,
  onInc,
  size = "md",
  accent = "black",
}: {
  value: number | string;
  onDec: () => void;
  onInc: () => void;
  size?: keyof typeof BTN;
  accent?: "black" | "blue";
}) {
  const plus = accent === "blue" ? "bg-blue-500" : "bg-black";
  return (
    <div className="flex items-center gap-2 flex-shrink-0">
      <button onClick={onDec} className={`${BTN[size]} bg-inset text-ink flex items-center justify-center font-bold active:scale-95 transition`}>−</button>
      <span className={`${VAL[size]} text-center font-bold text-ink`}>{value}</span>
      <button onClick={onInc} className={`${BTN[size]} ${plus} text-white flex items-center justify-center font-bold active:scale-95 transition`}>+</button>
    </div>
  );
}

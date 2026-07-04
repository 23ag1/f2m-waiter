// Stable colour per category name — iiko-style category accents.
// No colour comes from the backend, so we derive a deterministic one from the name.
// `bg/border/text` = pastel set (chips, hint cards); `bar` = solid accent (the
// coloured left stripe on menu category tiles).

export interface CategoryColor {
  bg: string;
  border: string;
  text: string;
  bar: string;
}

const PALETTE: CategoryColor[] = [
  { bg: "bg-red-100", border: "border-red-200", text: "text-red-700", bar: "bg-red-500" },
  { bg: "bg-orange-100", border: "border-orange-200", text: "text-orange-700", bar: "bg-orange-500" },
  { bg: "bg-amber-100", border: "border-amber-200", text: "text-amber-700", bar: "bg-amber-500" },
  { bg: "bg-yellow-100", border: "border-yellow-200", text: "text-yellow-700", bar: "bg-yellow-500" },
  { bg: "bg-lime-100", border: "border-lime-200", text: "text-lime-700", bar: "bg-lime-500" },
  { bg: "bg-green-100", border: "border-green-200", text: "text-green-700", bar: "bg-green-500" },
  { bg: "bg-emerald-100", border: "border-emerald-200", text: "text-emerald-700", bar: "bg-emerald-500" },
  { bg: "bg-teal-100", border: "border-teal-200", text: "text-teal-700", bar: "bg-teal-500" },
  { bg: "bg-cyan-100", border: "border-cyan-200", text: "text-cyan-700", bar: "bg-cyan-500" },
  { bg: "bg-sky-100", border: "border-sky-200", text: "text-sky-700", bar: "bg-sky-500" },
  { bg: "bg-blue-100", border: "border-blue-200", text: "text-blue-700", bar: "bg-blue-500" },
  { bg: "bg-indigo-100", border: "border-indigo-200", text: "text-indigo-700", bar: "bg-indigo-500" },
  { bg: "bg-violet-100", border: "border-violet-200", text: "text-violet-700", bar: "bg-violet-500" },
  { bg: "bg-purple-100", border: "border-purple-200", text: "text-purple-700", bar: "bg-purple-500" },
  { bg: "bg-fuchsia-100", border: "border-fuchsia-200", text: "text-fuchsia-700", bar: "bg-fuchsia-500" },
  { bg: "bg-pink-100", border: "border-pink-200", text: "text-pink-700", bar: "bg-pink-500" },
  { bg: "bg-rose-100", border: "border-rose-200", text: "text-rose-700", bar: "bg-rose-500" },
];

export function categoryColor(name: string): CategoryColor {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

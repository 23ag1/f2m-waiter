// Stable pastel colour per category name — iiko-style coloured category tiles.
// No colour comes from the backend, so we derive a deterministic one from the name.

const PALETTE: { bg: string; border: string; text: string }[] = [
  { bg: "bg-red-100", border: "border-red-200", text: "text-red-700" },
  { bg: "bg-orange-100", border: "border-orange-200", text: "text-orange-700" },
  { bg: "bg-amber-100", border: "border-amber-200", text: "text-amber-700" },
  { bg: "bg-yellow-100", border: "border-yellow-200", text: "text-yellow-700" },
  { bg: "bg-lime-100", border: "border-lime-200", text: "text-lime-700" },
  { bg: "bg-green-100", border: "border-green-200", text: "text-green-700" },
  { bg: "bg-emerald-100", border: "border-emerald-200", text: "text-emerald-700" },
  { bg: "bg-teal-100", border: "border-teal-200", text: "text-teal-700" },
  { bg: "bg-cyan-100", border: "border-cyan-200", text: "text-cyan-700" },
  { bg: "bg-sky-100", border: "border-sky-200", text: "text-sky-700" },
  { bg: "bg-blue-100", border: "border-blue-200", text: "text-blue-700" },
  { bg: "bg-indigo-100", border: "border-indigo-200", text: "text-indigo-700" },
  { bg: "bg-violet-100", border: "border-violet-200", text: "text-violet-700" },
  { bg: "bg-purple-100", border: "border-purple-200", text: "text-purple-700" },
  { bg: "bg-fuchsia-100", border: "border-fuchsia-200", text: "text-fuchsia-700" },
  { bg: "bg-pink-100", border: "border-pink-200", text: "text-pink-700" },
  { bg: "bg-rose-100", border: "border-rose-200", text: "text-rose-700" },
];

export function categoryColor(name: string): { bg: string; border: string; text: string } {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

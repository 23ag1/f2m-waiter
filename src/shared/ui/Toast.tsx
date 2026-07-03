"use client";

export interface ToastState {
  msg: string;
  type: "ok" | "err";
}

// Single toast presentation — was hand-copied in 6 screens.
export function Toast({ toast }: { toast: ToastState | null }) {
  if (!toast) return null;
  return (
    <div
      className={`fixed top-6 left-1/2 -translate-x-1/2 z-[70] px-5 py-3 rounded-2xl shadow-lg text-sm font-semibold animate-fade-in ${
        toast.type === "ok" ? "bg-green-500 text-white" : "bg-red-500 text-white"
      }`}
    >
      {toast.msg}
    </div>
  );
}

"use client";

import type { ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/shared/lib/utils";

// App button on our tokens (see DESIGN-SYSTEM.md). Covers the real CTA shapes:
// blue primary, black dark, outline «Отмена», danger, ghost. 4pt grid throughout.
const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap select-none transition active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary: "bg-blue-500 text-white",
        dark: "bg-black text-white",
        outline: "border border-hair text-ink-muted hover:bg-inset",
        danger: "text-red-500",
        ghost: "text-ink hover:bg-inset",
      },
      size: {
        md: "py-3 rounded-xl text-sm font-semibold",
        lg: "py-4 rounded-2xl text-base font-bold",
      },
      fullWidth: {
        true: "w-full",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, fullWidth, ...props }: ButtonProps) {
  return (
    <button className={cn(buttonVariants({ variant, size, fullWidth, className }))} {...props} />
  );
}

export { buttonVariants };

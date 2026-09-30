import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-700", {
  variants: { variant: { default: "bg-[var(--accent)] text-white hover:brightness-90", secondary: "bg-[var(--surface)] border border-[var(--line)] hover:bg-[var(--muted)]", ghost: "hover:bg-[var(--muted)]", danger: "bg-red-50 text-red-800 border border-red-200 hover:bg-red-100" }, size: { default: "h-9 px-3", sm: "h-8 px-2 text-xs", icon: "h-8 w-8" } },
  defaultVariants: { variant: "default", size: "default" },
});
export function Button({ className, variant, size, asChild = false, ...props }: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

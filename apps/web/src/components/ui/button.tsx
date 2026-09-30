import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Icônes fixées à 16 px ; anneau de focus sur le jeton --ring (theme.css).
const buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium transition-colors motion-reduce:transition-none disabled:pointer-events-none disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0", {
  variants: {
    variant: {
      default: "bg-primary text-primary-foreground hover:bg-primary/90",
      secondary: "border border-border bg-card text-foreground hover:bg-muted",
      ghost: "text-foreground hover:bg-muted",
      danger: "border border-destructive/30 bg-destructive-muted text-destructive hover:bg-destructive/15",
    },
    size: { default: "h-9 px-3 text-sm", sm: "h-8 px-2 text-xs", icon: "size-8" },
  },
  defaultVariants: { variant: "default", size: "default" },
});
export function Button({ className, variant, size, asChild = false, ...props }: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

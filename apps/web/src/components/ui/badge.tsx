import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Un ton par valeur de `Tone` (lib/status.ts) ; les couples fond/texte sont contrôlés
// à 4,5:1 par tests/unit/ui-guards.test.ts. Le texte du badge porte seul le sens.
const badgeVariants = cva("inline-flex items-center gap-1 whitespace-nowrap rounded-sm px-2 py-0.5 text-[11px] font-medium leading-4 [&_svg]:size-3 [&_svg]:shrink-0", {
  variants: {
    tone: {
      neutral: "bg-muted text-muted-foreground",
      info: "bg-info-muted text-info",
      success: "bg-success-muted text-success",
      warning: "bg-warning-muted text-warning",
      destructive: "bg-destructive-muted text-destructive",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({ className, tone, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-[var(--accent)]/10 text-[var(--accent)]",
        secondary:
          "bg-[var(--background-elevated)] text-[var(--foreground-secondary)]",
        success: "bg-[var(--success)]/10 text-[var(--success)]",
        warning: "bg-[var(--warning)]/10 text-[var(--warning)]",
        error: "bg-[var(--error)]/10 text-[var(--error)]",
        outline: "border border-[var(--border)] text-[var(--foreground)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };

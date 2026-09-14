import React from "react";
import { cn } from "@/lib/utils";
import { SERIF_SECTION } from "./tokens";

/**
 * One Fraunces sentence between two hairlines, and at most one action. No
 * dashed box, no illustration: an empty desk is a fact, not a failure.
 */
export function EmptyState({
  children,
  action,
  className,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3.5 border-y border-[var(--bz-border)] py-9",
        className,
      )}
    >
      <p
        className="text-[20px] tracking-[-0.02em] text-[var(--tx-secondary)]"
        style={SERIF_SECTION}
      >
        {children}
      </p>
      {action}
    </div>
  );
}

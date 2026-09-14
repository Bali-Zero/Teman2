import React from "react";
import { cn } from "@/lib/utils";

/**
 * A quiet notice. `tone="you"` is the only alarming variant kita has — copper
 * text on a copper hairline plus the caller's WORDS, never a filled red row.
 *
 * Promoted from (workspace)/garuda-voa/r19.tsx, which keeps its page-local
 * copy until K5 migrates that console onto this module.
 */
export function Notice({
  children,
  tone = "you",
  role,
  className,
}: {
  children: React.ReactNode;
  tone?: "you" | "ok" | "wait";
  role?: "alert" | "status";
  className?: string;
}) {
  return (
    <div
      role={role}
      className={cn(
        "rounded-lg border bg-[var(--bz-card)] px-4 py-3 text-sm",
        tone === "you" &&
          "border-[var(--bz-copper)] text-[var(--bz-copper-text)]",
        tone === "ok" &&
          "border-[var(--state-success)] text-[var(--state-success)]",
        tone === "wait" &&
          "border-[var(--bz-border)] text-[var(--tx-secondary)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

import React from "react";
import { cn } from "@/lib/utils";

/**
 * The finished mark: a rotated forest outline reading "Reviewed · Bali Zero ·
 * date". It binds ONLY where a real review timestamp exists on the record, so
 * a caller without one must not render it — there is no "probably reviewed".
 */
export function Stamp({
  label = "Reviewed",
  by = "Bali Zero",
  on,
  className,
}: {
  label?: string;
  by?: string;
  /** Already formatted by the caller, in the caller's locale. */
  on: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex -rotate-6 items-center gap-[7px] whitespace-nowrap rounded-sm",
        "border border-[var(--state-success)] bg-transparent px-2.5 py-1.5",
        "text-[9px] font-[650] uppercase leading-none tracking-[0.16em] text-[var(--state-success)]",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="h-[5px] w-[5px] shrink-0 rounded-full bg-current"
      />
      {label} · {by} · {on}
    </span>
  );
}

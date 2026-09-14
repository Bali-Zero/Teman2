import React from "react";
import { cn } from "@/lib/utils";

/**
 * The stamp: a rotated outline reading a fact, never a guess. Two tones:
 *
 * - `tone="forest"` — "Reviewed · Bali Zero · <date>" — binds ONLY where a
 *   real review timestamp exists on the record, so a caller without one
 *   renders NOTHING rather than a stamp with a blank date. There is no
 *   "probably reviewed".
 * - `tone="copper"` — "Needs you" — binds ONLY to an ownership predicate the
 *   caller already computed, never to a status string or a date. Without
 *   `owned === true` it renders NOTHING. Copper stamps are DETAIL-PAGE
 *   only — a list row uses `StatePill`, not this.
 */
export function Stamp({
  tone = "forest",
  label,
  by = "Bali Zero",
  on,
  owned,
  className,
}: {
  tone?: "forest" | "copper";
  label?: string;
  by?: string;
  /** Already formatted by the caller, in the caller's locale. Required for `tone="forest"`. */
  on?: string;
  /** An ownership predicate the caller computed. Required (`=== true`) for `tone="copper"`. */
  owned?: boolean;
  className?: string;
}) {
  if (tone === "forest" && !on) return null;
  if (tone === "copper" && owned !== true) return null;

  return (
    <span
      className={cn(
        "inline-flex -rotate-6 items-center gap-2 whitespace-nowrap rounded-[2px] border-[1.5px]",
        "bg-transparent px-[11px] py-1.5 text-[11px] font-[750] uppercase leading-none tracking-[0.14em]",
        tone === "forest" &&
          "border-[var(--state-success)] text-[var(--state-success)]",
        tone === "copper" &&
          "border-[var(--bz-copper-text)] text-[var(--bz-copper-text)]",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="h-[6px] w-[6px] shrink-0 rotate-45 bg-current"
      />
      {tone === "forest" ? (
        <>
          {label ?? "Reviewed"} · {by} · {on}
        </>
      ) : (
        (label ?? "Needs you")
      )}
    </span>
  );
}

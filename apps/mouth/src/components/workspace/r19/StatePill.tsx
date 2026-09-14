import React from "react";
import { cn } from "@/lib/utils";
import { PILL_SELECTED, PILL_SQUARE, PILL_TONE, type PillTone } from "./tokens";

const BASE = cn(
  "inline-flex h-6 items-center gap-1.5 whitespace-nowrap border px-2.5",
  PILL_SQUARE,
  "text-[10px] font-[650] uppercase tracking-[0.12em] bg-transparent",
);

/**
 * The one status vocabulary: four meanings plus the `ink` tone, always with a
 * WORD, never a colour alone.
 *
 * A row pill is an inert `<span>` — square (2px radius, never a circle) with
 * a diamond pip. Pass `pressed` and it becomes a focusable
 * `<button aria-pressed>` — that is the desk strip's FILTER, the one place a
 * pill is a choice rather than a report, and the only place it is filled.
 * v2 fills it INK with paper text (was slate) and it also shows a leading
 * tick, because fill alone cannot carry the difference. Copper is never a
 * background here.
 */
export function StatePill({
  tone,
  label,
  pressed,
  onClick,
  className,
}: {
  tone: PillTone;
  label: string;
  pressed?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const mark =
    pressed === true ? (
      <span aria-hidden="true" className="text-[11px] leading-none">
        ✓
      </span>
    ) : (
      <span
        aria-hidden="true"
        className={cn(
          "h-[6px] w-[6px] shrink-0 rotate-45 bg-current",
          tone === "ink" && "hidden",
        )}
      />
    );

  if (pressed === undefined) {
    return (
      <span className={cn(BASE, PILL_TONE[tone], className)}>
        {mark}
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        BASE,
        "cursor-pointer",
        pressed ? PILL_SELECTED : PILL_TONE[tone],
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]",
        className,
      )}
    >
      {mark}
      {label}
    </button>
  );
}

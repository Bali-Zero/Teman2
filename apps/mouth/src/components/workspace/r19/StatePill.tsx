import React from "react";
import { cn } from "@/lib/utils";
import { PILL_SELECTED, PILL_TONE, type PillTone } from "./tokens";

const BASE =
  "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 " +
  "text-[10px] font-[650] uppercase tracking-[0.12em] bg-transparent";

/**
 * The one status vocabulary: four meanings plus the `ink` tone, always with a
 * WORD, never a colour alone.
 *
 * A row pill is an inert `<span>` with a dot. Pass `pressed` and it becomes a
 * focusable `<button aria-pressed>` — that is the desk strip's FILTER, the one
 * place a pill is a choice rather than a report, and the only place it is
 * filled. The fill is slate and it also shows a leading tick, because fill
 * alone cannot carry the difference.
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
          "h-1.5 w-1.5 shrink-0 rounded-full bg-current",
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

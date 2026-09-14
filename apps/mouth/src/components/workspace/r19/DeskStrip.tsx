import React from "react";
import { cn } from "@/lib/utils";
import { NUMERAL_COUNT, SERIF, TABULAR } from "./tokens";

/**
 * The 44px bar over every kita list: a Fraunces count, a FILTER group of
 * `aria-pressed` pills, and whatever the page puts on the right (a search box,
 * a view toggle, a primary action).
 *
 * It is sticky under the header. The filters are a `role="group"` so the label
 * "FILTER" names them for a screen reader as well as for the eye — the
 * selected pill's ink fill with paper text (that pairing lives in
 * `StatePill`; this strip only groups the pills) is a choice, and a choice
 * needs a name.
 */
export function DeskStrip({
  count,
  countLabel,
  filters,
  right,
  stickyTop,
  className,
}: {
  count?: React.ReactNode;
  countLabel?: string;
  filters?: React.ReactNode;
  right?: React.ReactNode;
  /** CSS length for `top`. Defaults to the 48px shell header. */
  stickyTop?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "sticky z-20 flex h-11 items-center gap-2.5 border-y border-[var(--bz-border)] bg-[var(--bz-base)] px-0.5",
        className,
      )}
      style={{ top: stickyTop ?? "var(--bz-header-height, 48px)" }}
    >
      {count !== undefined ? (
        <span
          className={cn("whitespace-nowrap", NUMERAL_COUNT)}
          style={{ ...SERIF, ...TABULAR }}
          aria-label={countLabel}
        >
          {count}
        </span>
      ) : null}
      {filters ? (
        <>
          <span className="shrink-0 text-[9px] font-[650] uppercase tracking-[0.16em] text-[var(--tx-secondary)]">
            Filter
          </span>
          <div
            role="group"
            aria-label="Filter"
            className="flex min-w-0 items-center gap-1.5 overflow-hidden"
          >
            {filters}
          </div>
        </>
      ) : null}
      {right ? (
        <div className="ml-auto flex shrink-0 items-center gap-2">{right}</div>
      ) : null}
    </div>
  );
}

import React from "react";
import { cn } from "@/lib/utils";
import { Numeral, type NumeralTone } from "./NumberedList";

/**
 * The ledger row / detail-section margin: an 18px Fraunces ordinal in a
 * fixed, right-aligned column, then a 1px vertical hairline separating it
 * from the content it numbers.
 *
 * `n` is RENDERED, never stored — the caller derives it from an index (a
 * running count over a filtered/sorted list, for instance) on every render;
 * this component owns no counter of its own.
 */
export function OrdinalMargin({
  n,
  tone = "wait",
  className,
}: {
  n: number;
  tone?: NumeralTone;
  className?: string;
}) {
  return (
    <div className={cn("flex shrink-0 items-stretch gap-2.5", className)}>
      <Numeral
        n={n}
        tone={tone}
        size="ordinal"
        className="w-[34px] shrink-0 text-right md:w-[42px]"
      />
      <span
        aria-hidden="true"
        className="w-px self-stretch bg-[var(--bz-border)]"
      />
    </div>
  );
}

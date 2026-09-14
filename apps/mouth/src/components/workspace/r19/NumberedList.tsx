import React from "react";
import { cn } from "@/lib/utils";
import {
  NUMERAL_COUNT,
  NUMERAL_KPI,
  NUMERAL_ORDINAL,
  SERIF,
  TABULAR,
  pad2,
} from "./tokens";

export type NumeralTone = "wait" | "you" | "done" | "ours";
export type NumeralSize = "kpi" | "count" | "ordinal";

const NUMERAL_SIZE: Record<NumeralSize, string> = {
  kpi: NUMERAL_KPI,
  count: NUMERAL_COUNT,
  ordinal: NUMERAL_ORDINAL,
};

/**
 * A Fraunces numeral, tabular, in one of three sizes — the 44/38 viewport-peak
 * KPI, the 22px desk-strip count, or the 18px 01/02/03 ordinal. Copper when
 * the record is asking for the viewer, forest when done, slate for
 * "ours"/moving, muted otherwise — the numeral is the ownership signal, and
 * it always sits beside a word.
 */
export function Numeral({
  n,
  tone = "wait",
  size = "ordinal",
  className,
}: {
  n: number;
  tone?: NumeralTone;
  size?: NumeralSize;
  className?: string;
}) {
  return (
    <span
      className={cn(
        NUMERAL_SIZE[size],
        tone === "you" && "text-[var(--bz-copper-text)]",
        tone === "done" && "text-[var(--state-success)]",
        tone === "ours" && "text-[var(--state-info)]",
        tone === "wait" && "text-[var(--tx-secondary)]",
        className,
      )}
      style={{ ...SERIF, ...TABULAR }}
    >
      {pad2(n)}
    </span>
  );
}

export type NumberedItem = {
  /** Stable key; the page's own id, never the index. */
  id: string;
  title: React.ReactNode;
  detail?: React.ReactNode;
  tone?: NumeralTone;
  right?: React.ReactNode;
};

/**
 * Hairline rows numbered 01, 02, 03 — the gate's three sections, a process
 * stepper, an approval queue. Numbering starts at 1 and is presentational:
 * the caller supplies the order.
 *
 * `owned` renders the owned-queue rule — a 4px copper BORDER (never a fill)
 * on the `<ol>` itself — and is also the ownership margin's default: an
 * item's ordinal is copper when the list is `owned` OR the item's own
 * `tone === "you"`, and otherwise takes the item's own tone (default
 * `wait`). Implemented exactly as `item.tone ?? (owned ? "you" : "wait")`.
 */
export function NumberedList({
  items,
  owned = false,
  className,
}: {
  items: NumberedItem[];
  owned?: boolean;
  className?: string;
}) {
  return (
    <ol
      className={cn(
        "flex flex-col",
        owned && "border-l-4 border-[var(--bz-copper)] pl-[11px] md:pl-[15px]",
        className,
      )}
    >
      {items.map((item, i) => {
        const ordinalTone: NumeralTone = item.tone ?? (owned ? "you" : "wait");
        return (
          <li
            key={item.id}
            className="flex gap-3.5 border-b border-[var(--bz-border)] py-2.5 first:border-t"
          >
            <Numeral
              n={i + 1}
              tone={ordinalTone}
              size="ordinal"
              className="w-[26px] shrink-0 text-right"
            />
            <div className="min-w-0 flex-1">
              <span className="block font-semibold">{item.title}</span>
              {item.detail ? (
                <span className="mt-0.5 block text-[12px] text-[var(--tx-secondary)]">
                  {item.detail}
                </span>
              ) : null}
            </div>
            {item.right ? (
              <div className="flex shrink-0 items-center">{item.right}</div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

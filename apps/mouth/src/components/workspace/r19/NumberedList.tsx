import React from "react";
import { cn } from "@/lib/utils";
import { SERIF, TABULAR, pad2 } from "./tokens";

/**
 * A Fraunces 01/02/03 numeral. Copper when the step is the one asking for the
 * viewer, forest when it is done, muted otherwise — the numeral is the
 * ownership signal, and it always sits beside a word.
 */
export function Numeral({
  n,
  tone = "wait",
  className,
}: {
  n: number;
  tone?: "wait" | "you" | "done";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "text-[16px] leading-none tracking-[-0.02em]",
        tone === "you" && "text-[var(--bz-copper-text)]",
        tone === "done" && "text-[var(--state-success)]",
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
  tone?: "wait" | "you" | "done";
  right?: React.ReactNode;
};

/**
 * Hairline rows numbered 01, 02, 03 — the gate's three sections, a process
 * stepper, an approval queue. Numbering starts at 1 and is presentational:
 * the caller supplies the order.
 */
export function NumberedList({
  items,
  className,
}: {
  items: NumberedItem[];
  className?: string;
}) {
  return (
    <ol className={cn("flex flex-col", className)}>
      {items.map((item, i) => (
        <li
          key={item.id}
          className="flex gap-3.5 border-b border-[var(--bz-border)] py-2.5 first:border-t"
        >
          <Numeral
            n={i + 1}
            tone={item.tone}
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
      ))}
    </ol>
  );
}

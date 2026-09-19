import React from "react";
import { cn } from "@/lib/utils";

/**
 * A validity bar for a document's issue→expiry window: a hairline track with
 * an ink fill for the elapsed share — the fill's own right edge IS "today",
 * so no separate marker is drawn (this folder's copper allow-list is closed
 * to the `Stamp` primitive only; a raw `--bz-copper` tick here would not be
 * on it, see the R3c guard in `__tests__/client-detail-desk.test.tsx`).
 *
 * Pure day-math on the two REAL dates the caller already resolved from its
 * data — this component never formats a date, only measures one, so it
 * carries no SSR-hydration risk from `new Date()` text output (see
 * IMPLEMENTER-RULES.md "no `new Date()` FORMATTING inside components").
 */
export function ValidityTrack({
  issueDate,
  expiryDate,
  className,
}: {
  /** ISO date string — the document's real issue date. */
  issueDate: string;
  /** ISO date string — the document's real expiry date. */
  expiryDate: string;
  className?: string;
}) {
  const issued = new Date(issueDate).getTime();
  const expires = new Date(expiryDate).getTime();
  const now = Date.now();
  const total = expires - issued;
  const elapsedMs = Math.min(Math.max(now - issued, 0), Math.max(total, 0));
  const pct = total > 0 ? (elapsedMs / total) * 100 : 0;
  const daysTotal = Math.max(0, Math.round(total / 86400000));
  const daysElapsed = Math.max(0, Math.round(elapsedMs / 86400000));
  const daysRemaining = Math.max(0, daysTotal - daysElapsed);

  return (
    <div
      role="img"
      aria-label={`${daysElapsed} of ${daysTotal} days elapsed, ${daysRemaining} remaining`}
      className={cn(
        "relative my-3.5 h-[4px] rounded-[2px] bg-[var(--bz-border)]",
        className,
      )}
    >
      <i
        className="absolute inset-y-0 left-0 block rounded-[2px] bg-[var(--tx-pure)] not-italic"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

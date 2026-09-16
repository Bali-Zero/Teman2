"use client";

import { cn } from "@/lib/utils";
import { PILL_SELECTED, SERIF, TABULAR } from "@/components/workspace/r19";

import { COUNTER_STATUSES, type StatusFilter } from "./types";
import type { StatusCounts } from "./useStatusCounters";

interface Props {
  counts: StatusCounts;
  loading: boolean;
  /** "" = every client; shown so the reviewer knows what the numbers cover. */
  clientId: string;
  /** Clicking a tile moves the status filter to it. */
  onSelect: (status: StatusFilter) => void;
  activeStatus: StatusFilter;
}

/**
 * A hairline KPI band: one row of cells divided by 1px rules, each cell a
 * small uppercase label above a large tabular Fraunces numeral. No card
 * chrome, no rounded corners, no drop shadow — the unit is the cell, not a
 * box around it. Two columns below `md`, four across on a desk.
 *
 * Selection reuses `PILL_SELECTED` verbatim — the SAME ink-fill treatment
 * `StatePill`'s `pressed` gives the filter strip on this page — never
 * copper: copper means "the viewer is the next actor", never "this control
 * is selected". Text colour on the label and numeral is set explicitly
 * (rather than left to inherit through the button) so the swap is
 * deterministic regardless of Tailwind's utility generation order.
 */
export function StatusCounters({
  counts,
  loading,
  clientId,
  onSelect,
  activeStatus,
}: Props) {
  return (
    <section className="mb-4" aria-label="Status counters">
      <p className="mb-2 text-xs" style={{ color: "var(--bz-text-3)" }}>
        {clientId ? `Client ${clientId}` : "All clients"}
      </p>
      <div className="grid grid-cols-2 border-y border-[var(--bz-border)] md:grid-cols-4">
        {COUNTER_STATUSES.map((status) => {
          const value = counts[status];
          const selected = activeStatus === status;
          return (
            <button
              key={status}
              type="button"
              onClick={() => onSelect(status)}
              aria-label={`Filter by ${status}`}
              aria-pressed={selected}
              className={cn(
                "min-w-0 px-4 py-3 text-left",
                "[&:nth-child(odd)]:border-r [&:nth-child(-n+2)]:border-b",
                "md:[&:nth-child(-n+2)]:border-b-0 md:[&:not(:nth-child(4))]:border-r",
                selected ? PILL_SELECTED : "bg-transparent",
              )}
              style={{
                borderColor: selected ? "var(--tx-pure)" : "var(--bz-border)",
              }}
            >
              <span
                className="block text-[10px] font-[650] uppercase tracking-[0.14em]"
                style={{
                  color: selected ? "var(--bz-base)" : "var(--tx-secondary)",
                }}
              >
                {status}
              </span>
              <span
                className="mt-1.5 block text-[28px] leading-none tracking-[-0.02em]"
                style={{
                  ...SERIF,
                  ...TABULAR,
                  color: selected ? "var(--bz-base)" : "var(--tx-pure)",
                }}
                data-testid={`counter-${status}`}
              >
                {loading && value === undefined
                  ? "…"
                  : value === undefined
                    ? "—"
                    : value}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

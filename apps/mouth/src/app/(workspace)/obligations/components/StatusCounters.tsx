"use client";

import { CARD, COUNTER_STATUSES, type StatusFilter } from "./types";
import type { StatusCounts } from "./useStatusCounters";

const SWATCH: Record<string, string> = {
  proposed: "var(--bz-accent)",
  approved: "var(--state-success)",
  rejected: "var(--state-danger)",
  alerted: "var(--state-warning)",
};

interface Props {
  counts: StatusCounts;
  loading: boolean;
  /** "" = every client; shown so the reviewer knows what the numbers cover. */
  clientId: string;
  /** Clicking a tile moves the status filter to it. */
  onSelect: (status: StatusFilter) => void;
  activeStatus: StatusFilter;
}

/** Row counts per status for the current client filter (four parallel reads). */
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
      <div className="flex flex-wrap gap-3">
        {COUNTER_STATUSES.map((status) => {
          const value = counts[status];
          return (
            <button
              key={status}
              type="button"
              onClick={() => onSelect(status)}
              aria-label={`Filter by ${status}`}
              aria-pressed={activeStatus === status}
              className="min-w-28 rounded-xl border px-4 py-2 text-left"
              style={{
                ...CARD,
                borderColor:
                  activeStatus === status ? SWATCH[status] : "var(--bz-border)",
              }}
            >
              <span
                className="block text-xs capitalize"
                style={{ color: "var(--bz-text-3)" }}
              >
                {status}
              </span>
              <span
                className="block text-xl font-semibold"
                style={{ color: "var(--bz-text-1)" }}
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

"use client";

import { CARD, COUNTER_STATUSES, type StatusFilter } from "./types";
import type { StatusCounts } from "./useStatusCounters";

/**
 * - `proposed` is copper because the row renders the viewer's own Approve and
 *   Reject controls, so the viewer is demonstrably the next actor;
 * - `alerted` is copper by the standing ruling in `concept/DISPOSITION.md`
 *   C11 ("obligations `alerted` -> copper, `rejected` -> waiting"), recorded
 *   as a RULING and not as a derivation this row can prove.
 *
 * `approved` is forest (done). `rejected` is a TERMINAL state, so it is muted
 * — never danger — and carries its own word (the tile's label). No tile takes
 * a tone from a date; urgency lives on the due date, in warning.
 */
const SWATCH: Record<string, string> = {
  proposed: "var(--bz-copper-text)",
  approved: "var(--state-success)",
  rejected: "var(--tx-secondary)",
  alerted: "var(--bz-copper-text)",
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

"use client";

import { Home, Landmark, Scale } from "lucide-react";
import { getCopy } from "@/lib/secondhome-studio/copy";

const COLUMNS = ["deposit", "property", "senior"] as const;

const COLUMN_ICONS = {
  deposit: Landmark,
  property: Home,
  senior: Scale,
} as const;
const ROWS = [
  "capital",
  "liquidity",
  "whatQualifies",
  "currentStatus",
] as const;

export interface RouteComparatorProps {
  /** Shown prominently when the plan's route is "unsure" (spec §3 row 8) —
   *  a highlighted border, not a layout reorder. */
  highlight?: boolean;
}

/** Static, honest deposit vs property vs senior comparison table (spec §5).
 *  Wrapped in an overflow-x container so a narrow viewport scrolls the
 *  table, never the page. */
export function RouteComparator({ highlight = false }: RouteComparatorProps) {
  return (
    <section
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: highlight
          ? "2px solid var(--accent-funnel)"
          : "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
      }}
    >
      <h2
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.2rem, 3vw, 1.5rem)",
          color: "var(--text-primary)",
        }}
      >
        Compare the routes
      </h2>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th scope="col" style={{ padding: "var(--space-2, 0.5rem)" }} />
              {COLUMNS.map((c) => {
                const ColumnIcon = COLUMN_ICONS[c];
                return (
                  <th
                    key={c}
                    scope="col"
                    style={{
                      textAlign: "left",
                      padding: "var(--space-2, 0.5rem)",
                      color: "var(--text-primary)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "var(--space-2, 0.5rem)",
                      }}
                    >
                      <ColumnIcon
                        size={18}
                        strokeWidth={1.5}
                        aria-hidden
                        style={{
                          flexShrink: 0,
                          color: "var(--color-text-muted)",
                        }}
                      />
                      {getCopy(`routeComparator.columns.${c}.title`)}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr
                key={r}
                style={{ borderTop: "1px solid var(--color-border-subtle)" }}
              >
                <th
                  scope="row"
                  style={{
                    textAlign: "left",
                    padding: "var(--space-2, 0.5rem)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                  }}
                >
                  {getCopy(`routeComparator.rows.${r}.label`)}
                </th>
                {COLUMNS.map((c) => (
                  <td
                    key={c}
                    style={{
                      padding: "var(--space-2, 0.5rem)",
                      color: "var(--text-primary)",
                      fontSize: "var(--text-sm, 0.9rem)",
                    }}
                  >
                    {getCopy(`routeComparator.rows.${r}.${c}`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

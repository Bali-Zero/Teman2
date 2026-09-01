"use client";

import { CircleDashed, Home, Landmark, Scale } from "lucide-react";
import type { ReactNode } from "react";
import { getCopy } from "@/lib/secondhome-studio/copy";

const ROUTES = ["deposit", "property", "senior"] as const;
type Route = (typeof ROUTES)[number];

const ROUTE_ICONS = {
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
type Row = (typeof ROWS)[number];

export interface RouteComparatorProps {
  /** Shown prominently when the plan's route is "unsure" (spec §3 row 8) —
   *  a highlighted border, not a layout reorder. */
  highlight?: boolean;
}

function RouteHeading({ route }: { route: Route }): ReactNode {
  const RouteIcon = ROUTE_ICONS[route];

  return (
    <span className="bz-shs-route-heading">
      <span className="bz-shs-route-icon" aria-hidden="true">
        <RouteIcon size={24} strokeWidth={1.7} />
      </span>
      <span>{getCopy(`routeComparator.columns.${route}.title`)}</span>
    </span>
  );
}

function RouteValue({ route, row }: { route: Route; row: Row }): ReactNode {
  const value = getCopy(`routeComparator.rows.${row}.${route}`);

  if (route === "property" && row === "currentStatus") {
    return (
      <span className="bz-shs-route-status">
        <CircleDashed size={17} strokeWidth={2} aria-hidden="true" />
        <span>{value}</span>
      </span>
    );
  }

  return value;
}

/**
 * Static, honest deposit vs property vs senior comparison.
 *
 * The native table is shown on wide screens. At 760px and below it is removed
 * from layout and the same data is presented as explicit label/value cards;
 * the inactive representation is `display: none`, including for assistive tech.
 */
export function RouteComparator({ highlight = false }: RouteComparatorProps) {
  return (
    <section
      className="bz-shs-route-comparator"
      data-highlighted={highlight ? "true" : "false"}
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        minWidth: 0,
        width: "100%",
        maxWidth: "100%",
        boxSizing: "border-box",
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
          // R4 §3: Cormorant is display-only and never below 24px — under that,
          // low-DPI Android antialiasing shreds the serif.
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.5rem, 3vw, 1.75rem)",
          color: "var(--text-primary)",
        }}
      >
        Compare the routes
      </h2>

      <div className="bz-shs-route-table-view" data-comparison-view="table">
        <table aria-label="Second Home route comparison">
          <colgroup>
            <col className="bz-shs-route-criteria-column" />
            {ROUTES.map((route) => (
              <col key={route} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th scope="col">
                <span className="bz-shs-route-visually-hidden">
                  Comparison criterion
                </span>
              </th>
              {ROUTES.map((route) => (
                <th key={route} scope="col" data-route={route}>
                  <RouteHeading route={route} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row}>
                <th scope="row">
                  {getCopy(`routeComparator.rows.${row}.label`)}
                </th>
                {ROUTES.map((route) => (
                  <td key={route} data-route={route}>
                    <RouteValue route={route} row={row} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="bz-shs-route-cards"
        data-comparison-view="cards"
        role="group"
        aria-label="Second Home route comparison"
      >
        {ROUTES.map((route) => (
          <article
            className="bz-shs-route-card"
            data-route={route}
            data-route-card={route}
            key={route}
            aria-labelledby={`bz-shs-route-${route}-title`}
          >
            <h3 id={`bz-shs-route-${route}-title`}>
              <RouteHeading route={route} />
            </h3>
            <dl>
              {ROWS.map((row) => (
                <div className="bz-shs-route-pair" key={row}>
                  <dt>{getCopy(`routeComparator.rows.${row}.label`)}</dt>
                  <dd>
                    <RouteValue route={route} row={row} />
                  </dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>

      <style>{`
        .bz-shs-route-comparator {
          /* Literal hexes (not var()) so they match the design-system tokens
             exactly — RouteComparator.test.tsx regexes --route-copy/--route-label
             for a raw #hex, so an indirection breaks its AA-contrast assertion.
             #16213a == --text-primary, #475372 == --text-secondary. */
          --route-copy: #16213a;
          --route-label: #475372;
        }

        .bz-shs-route-table-view {
          min-width: 0;
        }

        .bz-shs-route-table-view table {
          width: 100%;
          table-layout: fixed;
          border-spacing: 0;
          border: 1px solid var(--color-border-subtle);
          border-radius: 10px;
        }

        .bz-shs-route-criteria-column {
          width: 18%;
        }

        .bz-shs-route-table-view th,
        .bz-shs-route-table-view td {
          min-width: 0;
          padding: var(--space-3, 0.75rem);
          text-align: left;
          overflow-wrap: break-word;
        }

        .bz-shs-route-table-view thead th {
          position: relative;
          height: 5.75rem;
          vertical-align: middle;
          color: var(--text-primary);
          background: var(--surface-raised);
        }

        .bz-shs-route-table-view thead th[data-route] {
          color: var(--route-copy);
          background: var(--route-tint);
        }

        .bz-shs-route-table-view thead th[data-route]::before,
        .bz-shs-route-card::before {
          position: absolute;
          inset: 0 0 auto;
          height: 4px;
          content: "";
        }

        .bz-shs-route-table-view thead th[data-route="deposit"]::before,
        .bz-shs-route-card[data-route="deposit"]::before {
          background: var(--route-accent);
        }

        .bz-shs-route-table-view thead th[data-route="property"]::before,
        .bz-shs-route-card[data-route="property"]::before {
          height: 6px;
          background: linear-gradient(
            to bottom,
            var(--route-accent) 0 2px,
            transparent 2px 4px,
            var(--route-accent) 4px 6px
          );
        }

        .bz-shs-route-table-view thead th[data-route="senior"]::before,
        .bz-shs-route-card[data-route="senior"]::before {
          background: repeating-linear-gradient(
            to right,
            var(--route-accent) 0 8px,
            transparent 8px 13px
          );
        }

        .bz-shs-route-table-view tbody th,
        .bz-shs-route-table-view tbody td {
          border-top: 1px solid var(--color-border-subtle);
          vertical-align: top;
        }

        .bz-shs-route-table-view tbody th {
          color: var(--color-text-muted);
          font-size: 0.76rem;
          font-weight: 700;
          line-height: 1.4;
          letter-spacing: 0.035em;
          text-transform: uppercase;
          background: var(--surface-raised);
        }

        .bz-shs-route-table-view tbody td {
          color: var(--route-copy);
          font-size: var(--text-sm, 0.9rem);
          line-height: 1.55;
          background: var(--route-tint);
        }

        .bz-shs-route-table-view [data-route="deposit"],
        .bz-shs-route-card[data-route="deposit"] {
          /* Literal (see comment above): #2a6f97 == --state-likely */
          --route-accent: #2a6f97;
          --route-tint: #e8eef2;
        }

        .bz-shs-route-table-view [data-route="property"],
        .bz-shs-route-card[data-route="property"] {
          /* Literal (see comment above): #7a5209 == --state-warning */
          --route-accent: #7a5209;
          --route-tint: #f8f2eb;
        }

        .bz-shs-route-table-view [data-route="senior"],
        .bz-shs-route-card[data-route="senior"] {
          /* DECLARED DEVIATION from the R4 token set (2026-08-31), recorded
             rather than left implicit. The other two routes map onto real
             tokens (--state-likely, --state-warning), but the third has no
             token left that does not LIE: the remaining state colours mean
             eligible / error, and both reds are reserved for structure and
             action. Rather than give a route a semantic colour it does not
             have, this keeps one desaturated hue that means nothing but
             "third row". Measured on carta 6.42, on its own tint 6.06, on
             white 6.95 — all clear. Safe because colour is NOT the signal
             here: the three routes are told apart by crest and by the top
             rule (dashed on the senior route), per R4 §4.5, and these tints
             carry no meaning alone. */
          --route-accent: #66517a;
          --route-tint: #f2eef5;
        }

        .bz-shs-route-heading {
          display: inline-flex;
          align-items: center;
          gap: var(--space-2, 0.5rem);
          min-width: 0;
          font-family: var(--font-serif, Georgia, serif);
          font-size: 1rem;
          font-weight: 700;
          line-height: 1.25;
        }

        .bz-shs-route-icon {
          display: inline-grid;
          flex: 0 0 42px;
          width: 42px;
          height: 42px;
          place-items: center;
          color: var(--route-accent);
          border: 2px solid currentColor;
        }

        [data-route="deposit"] .bz-shs-route-icon {
          border-radius: 50%;
          box-shadow: inset 0 0 0 3px var(--route-tint);
        }

        [data-route="property"] .bz-shs-route-icon {
          border-radius: 4px;
          border-bottom-width: 5px;
        }

        [data-route="senior"] .bz-shs-route-icon {
          width: 34px;
          height: 34px;
          margin: 4px;
          border-radius: 4px;
          transform: rotate(45deg);
        }

        [data-route="senior"] .bz-shs-route-icon svg {
          transform: rotate(-45deg);
        }

        .bz-shs-route-status {
          display: inline-flex;
          align-items: flex-start;
          gap: var(--space-2, 0.5rem);
          padding: 0.4rem 0.55rem;
          color: var(--state-warning);
          font-weight: 700;
          line-height: 1.4;
          background: #fff7e8;
          border: 1px dashed var(--state-warning);
          border-radius: 6px;
        }

        .bz-shs-route-status svg {
          flex: 0 0 auto;
          margin-top: 0.08rem;
        }

        .bz-shs-route-cards {
          display: none;
        }

        .bz-shs-route-visually-hidden {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border: 0;
        }

        @media (max-width: 760px) {
          .bz-shs-route-comparator {
            padding: var(--space-3, 1rem) !important;
          }

          .bz-shs-route-table-view {
            display: none;
          }

          .bz-shs-route-cards {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: var(--space-3, 1rem);
            min-width: 0;
          }

          .bz-shs-route-card {
            position: relative;
            min-width: 0;
            padding: var(--space-4, 1.5rem);
            color: var(--route-copy);
            background: var(--route-tint);
            border: 1px solid var(--color-border-subtle);
            border-radius: 10px;
          }

          .bz-shs-route-card h3 {
            margin: 0;
            overflow-wrap: break-word;
          }

          .bz-shs-route-card dl {
            display: grid;
            gap: 0;
            margin: var(--space-3, 1rem) 0 0;
          }

          .bz-shs-route-pair {
            min-width: 0;
            padding: var(--space-3, 0.75rem) 0;
            border-top: 1px solid var(--color-border-subtle);
          }

          .bz-shs-route-pair dt {
            color: var(--route-label);
            font-size: 0.76rem;
            font-weight: 700;
            line-height: 1.4;
            letter-spacing: 0.035em;
            text-transform: uppercase;
          }

          .bz-shs-route-pair dd {
            min-width: 0;
            margin: 0.35rem 0 0;
            color: var(--route-copy);
            font-size: var(--text-sm, 0.9rem);
            line-height: 1.55;
            overflow-wrap: break-word;
          }
        }
      `}</style>
    </section>
  );
}

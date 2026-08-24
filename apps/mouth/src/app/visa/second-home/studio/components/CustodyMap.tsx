"use client";

import { useState } from "react";

import { getCopy } from "@/lib/secondhome-studio/copy";

const STEPS = ["step1", "step2", "step3"] as const;

type Step = (typeof STEPS)[number];

function NodeIcon({ step }: { step: Step }) {
  const commonProps = {
    "aria-hidden": true,
    fill: "none",
    height: 28,
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.5,
    viewBox: "0 0 28 28",
    width: 28,
  };

  if (step === "step1") {
    return (
      <svg {...commonProps}>
        <circle cx="14" cy="8" r="3.5" />
        <path d="M6.5 22c.8-4.6 3.3-7 7.5-7s6.7 2.4 7.5 7" />
        <path d="M9 23h10" />
      </svg>
    );
  }

  if (step === "step2") {
    return (
      <svg {...commonProps}>
        <path d="M4.5 10.5 14 5l9.5 5.5" />
        <path d="M6.5 11.5h15M7.5 21.5h13M9 12v7.5M14 12v7.5M19 12v7.5" />
        <path d="M5 23h18" />
      </svg>
    );
  }

  return (
    <svg {...commonProps}>
      <path d="M8 3.5h8l5 5v16H8z" />
      <path d="M16 3.5v5h5M11.5 13h6M11.5 17h6" />
      <circle cx="18.5" cy="21" r="3" />
    </svg>
  );
}

/** Three-stage, interactive view of the deposit evidence path. All visible
 * copy comes from copy.ts so the Studio claim guard remains comprehensive. */
export function CustodyMap() {
  const [expandedStep, setExpandedStep] = useState<Step | null>(null);

  return (
    <section className="custody-map" aria-labelledby="custody-map-title">
      <header className="custody-header">
        <h2 id="custody-map-title">{getCopy("custody.eyebrow")}</h2>
      </header>

      <div
        className="custody-layout"
        role="group"
        aria-label={getCopy("custody.eyebrow")}
        aria-describedby="custody-map-intro"
      >
        <ol className="custody-flow">
          {STEPS.map((step, index) => {
            const isExpanded = expandedStep === step;
            const detailId = `custody-${step}-detail`;

            return (
              <li className="custody-flow-item" key={step}>
                <div className="custody-node" data-account={step === "step1"}>
                  <button
                    type="button"
                    aria-controls={detailId}
                    aria-expanded={isExpanded}
                    onClick={() => setExpandedStep(isExpanded ? null : step)}
                  >
                    <span className="custody-icon">
                      <NodeIcon step={step} />
                    </span>
                    <strong>{getCopy(`custody.steps.${step}.title`)}</strong>
                    <svg
                      aria-hidden
                      className="custody-chevron"
                      viewBox="0 0 16 16"
                    >
                      <path d="m4 6 4 4 4-4" />
                    </svg>
                  </button>
                  <p id={detailId} data-collapsed={!isExpanded}>
                    {getCopy(`custody.steps.${step}.body`)}
                  </p>
                </div>
                {index < STEPS.length - 1 ? (
                  <svg
                    aria-hidden
                    className="custody-arrow"
                    viewBox="0 0 40 18"
                  >
                    <path d="M2 9h33M29 3l6 6-6 6" />
                  </svg>
                ) : null}
              </li>
            );
          })}
        </ol>

        <aside className="custody-outside" id="custody-map-intro">
          <p>{getCopy("custody.intro")}</p>
        </aside>
      </div>

      <p className="custody-disclaimer">{getCopy("custody.disclaimer")}</p>

      <style jsx>{`
        .custody-map {
          display: grid;
          gap: 1.5rem;
          min-width: 0;
          padding: clamp(1.25rem, 3vw, 2rem);
          overflow: hidden;
          background: var(--surface-raised);
          border: 1px solid var(--color-border-subtle);
          border-radius: 12px;
          color: var(--text-primary);
          font-variant-numeric: tabular-nums;
        }

        .custody-header {
          padding-left: 1rem;
          border-left: 2px solid var(--color-border-subtle);
        }

        h2 {
          margin: 0;
          font-size: clamp(1.35rem, 3vw, 1.75rem);
          line-height: 1.2;
        }

        /* Screen breakpoint fix (2026-08-24): #4823 cured the print half of
         * this section's cramped-heading disease (@media print below); the
         * screen half was never measured and stayed broken. The old
         * side-by-side layout (3-column step flow | aside note) gave the
         * aside's own minmax(12rem, 0.3fr) track first claim on the row,
         * leaving the flow — and therefore each step card — squeezed at
         * every width up to this section's 1120px content cap, not just
         * near mobile. Measured on production: from 1024px to 1180px
         * viewport width, each heading's actual text box was 82-113px
         * wide (narrower than the word "application") and wrapped to 4-5
         * lines. Fix, two parts: (1) the aside now always sits BELOW the
         * step flow instead of beside it, so the flow keeps the full
         * section width at every viewport; (2) the step flow's own
         * 3-column -> 1-column stacking breakpoint moves from 760px to
         * 1024px (below), because even with the full section width a
         * 3-up card is still too narrow for the longest heading between
         * ~760-1024px — measured 4 lines at 860px on this fix's own first
         * draft. Both breakpoints now share the same 1024px threshold on
         * purpose: below it the flow is a single vertical column (full
         * width, roomy), at or above it there is enough per-card width
         * for 3 columns to stay <=2 lines up to the 1120px content cap
         * (measured 2 lines flat from 1180px to 1920px). */
        .custody-layout {
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          gap: clamp(1.75rem, 4vw, 2.5rem);
          min-width: 0;
        }

        .custody-flow {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 2.5rem;
          min-width: 0;
          margin: 0;
          padding: 0;
          list-style: none;
        }

        .custody-flow-item {
          position: relative;
          min-width: 0;
        }

        .custody-node {
          height: 100%;
          min-width: 0;
          background: var(--surface-raised);
          border: 1px solid var(--color-border-subtle);
          border-radius: 10px;
        }

        button {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          align-items: center;
          gap: 0.75rem;
          width: 100%;
          min-height: 6rem;
          padding: 1rem;
          color: var(--text-primary);
          text-align: left;
          background: transparent;
          border: 0;
          border-radius: 10px;
          cursor: pointer;
        }

        button:focus-visible {
          outline: 2px solid var(--text-primary);
          outline-offset: 3px;
        }

        .custody-icon {
          display: inline-grid;
          place-items: center;
          color: var(--color-text-muted);
        }

        .custody-node[data-account="true"] .custody-icon {
          color: var(--accent-funnel);
        }

        strong {
          min-width: 0;
          line-height: 1.35;
        }

        .custody-chevron {
          width: 16px;
          height: 16px;
          fill: none;
          stroke: var(--color-text-muted);
          stroke-linecap: round;
          stroke-linejoin: round;
          stroke-width: 1.5;
          transition: transform 180ms ease;
        }

        button[aria-expanded="true"] .custody-chevron {
          transform: rotate(180deg);
        }

        .custody-node > p {
          margin: 0;
          padding: 0 1rem 1rem;
          color: var(--color-text-muted);
          line-height: 1.6;
        }

        .custody-node > p[data-collapsed="true"] {
          display: none;
        }

        .custody-arrow {
          position: absolute;
          top: 3rem;
          left: calc(100% + 0.25rem);
          width: 2rem;
          height: 1.125rem;
          overflow: visible;
          fill: none;
          stroke: var(--color-text-muted);
          stroke-linecap: round;
          stroke-linejoin: round;
          stroke-width: 1.5;
        }

        /* No side connector by default: the aside sits BELOW the (still
         * horizontal, >1024px) step flow now, not beside it, so a
         * pointing-left dashed line has nothing on its left to point at.
         * The <=1024px breakpoint below restores a connector shaped for
         * that width's fully-stacked, single-column step list. */
        .custody-outside {
          position: relative;
          padding: 1rem;
          border: 1px dashed var(--color-border-subtle);
          border-radius: 10px;
        }

        .custody-outside p,
        .custody-disclaimer {
          margin: 0;
          color: var(--color-text-muted);
          line-height: 1.6;
        }

        .custody-disclaimer {
          font-size: 0.82rem;
          font-style: italic;
        }

        @media print {
          .custody-node > p[data-collapsed="true"] {
            display: block !important;
          }

          .custody-chevron {
            display: none !important;
          }

          /* Print fix (2026-08-24): at A4 print width the 3-column grid
           * squeezed each step into an unreadable ~55px ribbon (one word
           * per line), and the unbroken word "application" in step 2's
           * heading overflowed past this section's overflow:hidden and
           * was clipped mid-word ("applicatio|n"). Stack to one step per
           * row, full page width — same shape as the <=1024px screen
           * breakpoint below (760px when this comment was written; raised
           * 2026-08-24, see the .custody-layout comment above), but scoped
           * to @media print so it fires
           * regardless of what width the print engine's internal layout
           * pass actually computes (measured to differ from both the live
           * viewport and the @page content box — screen-narrow media
           * queries can't be trusted to also cover print).
           *
           * Arrows are hidden rather than rotated 90° like the mobile
           * breakpoint does: a printed page has no scroll/hover affordance,
           * consecutive steps are already separated by spacing and their
           * own headings, and a disconnected floating chevron between
           * full-width rows reads as clutter rather than flow. */
          .custody-layout,
          .custody-flow {
            grid-template-columns: minmax(0, 1fr) !important;
          }

          .custody-arrow {
            display: none !important;
          }

          .custody-outside::before {
            display: none !important;
          }
        }

        /* Was <=760px; raised to <=1024px (2026-08-24, see the .custody-layout
         * comment above) — the 3-column flow needs more per-card width
         * than 760-1024px viewports have to give without re-squeezing the
         * headings this whole fix exists to un-squeeze. */
        @media (max-width: 1024px) {
          .custody-flow {
            grid-template-columns: minmax(0, 1fr);
          }

          .custody-layout {
            gap: 2.5rem;
          }

          .custody-flow {
            gap: 2.25rem;
          }

          .custody-arrow {
            top: calc(100% + 0.55rem);
            left: 50%;
            transform: translateX(-50%) rotate(90deg);
          }

          /* Only at this width is the flow itself a single vertical
           * column (see .custody-flow override above), so a connector
           * pointing left from the aside to that column reads correctly.
           * Defined here (not as a default with per-width overrides)
           * because >1024px has no such column for it to point at. */
          .custody-outside::before {
            position: absolute;
            top: 1.5rem;
            right: 100%;
            width: 2rem;
            border-top: 1px dashed var(--color-border-subtle);
            content: "";
          }

          .custody-outside {
            width: calc(100% - 2rem);
            margin-left: 2rem;
          }
        }

        /* Narrow-phone tightening (2026-08-24): even full-width at this
         * point (single-column flow, see above), a small-phone viewport
         * still isn't wide enough for the longest heading ("Use the bank
         * evidence for your application") to clear 2 lines once the
         * button's own decorative chrome (icon + its gap + padding) is
         * subtracted — measured 3 lines at 360-390px on this fix's first
         * draft. The icon is aria-hidden decoration, so it is dropped
         * here rather than shrunk: that returns its full width (icon +
         * one gap) to the heading instead of only a few px. */
        @media (max-width: 480px) {
          .custody-icon {
            display: none;
          }

          /* Explicit 2-column track (text, chevron) now that the icon
           * column is gone — left as the original 3-column template's
           * implicit auto-placement, the heading would land in an "auto"
           * track sized by its own content instead of the flexible track,
           * which is the wrong track for something meant to wrap. */
          button {
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 0.5rem;
            padding: 0.85rem 0.65rem;
          }

          .custody-chevron {
            width: 14px;
            height: 14px;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .custody-chevron {
            transition: none;
          }
        }
      `}</style>
    </section>
  );
}

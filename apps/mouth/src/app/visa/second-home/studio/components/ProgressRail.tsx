"use client";

export interface ProgressRailProps {
  /** 1-indexed current step number. */
  step: number;
  /** Total step count for the CURRENT branch — adapts as answers narrow
   *  down the wizard sequence (spec §4: "M adapts to branch"). */
  total: number;
  /** One short name per step of the current branch ("Age", "Route", …).
   *  Optional — without it the rail still reads "Step N of M". */
  labels?: readonly string[];
}

type ProgressState = "complete" | "current" | "pending";

/** Labelled progress scale + "Step N of M" label. Pure/presentational —
 *  StudioApp owns all step-sequencing logic.
 *
 *  2026-09-24 design pass: the dashed "bathymetric" segments with square
 *  end-markers read as decoration (or as a broken line) and named nothing.
 *  Each segment is now a rounded bar with the step's name under it; reached
 *  and pending differ by SHAPE as well as colour (a 4px merah bar vs a 2px
 *  ink-tint track), and the current step carries a merah bar, a node and the ink label; done
 *  steps turn ink so the red marks only where you are. */
export function ProgressRail({ step, total, labels }: ProgressRailProps) {
  const safeTotal = Number.isFinite(total) ? Math.max(1, Math.trunc(total)) : 1;
  const safeStep = Number.isFinite(step)
    ? Math.min(safeTotal, Math.max(1, Math.trunc(step)))
    : 1;
  const names = labels && labels.length === safeTotal ? labels : undefined;
  const currentName = names?.[safeStep - 1];

  // The displayed checkpoint is already reached, so step 1 of 6 is one-sixth complete.
  const soundings = Array.from({ length: safeTotal }, (_, index) => {
    const sounding = index + 1;
    const state: ProgressState =
      sounding < safeStep
        ? "complete"
        : sounding === safeStep
          ? "current"
          : "pending";

    return { sounding, state, name: names?.[index] };
  });

  return (
    <div className="bz-shs-progress-rail">
      <div
        aria-label="Interview progress"
        aria-valuemax={safeTotal}
        aria-valuemin={0}
        aria-valuenow={safeStep}
        aria-valuetext={
          currentName
            ? `Step ${safeStep} of ${safeTotal}: ${currentName}`
            : undefined
        }
        className="bz-shs-progress-scale"
        role="progressbar"
        style={{
          gridTemplateColumns: `repeat(${safeTotal}, minmax(0, 1fr))`,
        }}
      >
        {soundings.map(({ sounding, state, name }) => (
          <span
            aria-hidden="true"
            className="bz-shs-progress-sounding"
            data-progress-reached={state !== "pending" ? "true" : "false"}
            data-state={state}
            key={sounding}
          >
            {name ? <span className="bz-shs-progress-name">{name}</span> : null}
          </span>
        ))}
      </div>
      <div className="bz-shs-progress-meta">
        <p aria-hidden="true" className="bz-shs-progress-count">
          Step {safeStep} of {safeTotal}
        </p>
        {currentName ? (
          <p aria-hidden="true" className="bz-shs-progress-current">
            {currentName}
          </p>
        ) : null}
      </div>
      <style>{`
        .bz-shs-progress-rail {
          --bz-shs-progress-track: color-mix(
            in srgb,
            var(--text-primary) 16%,
            transparent
          );
          display: grid;
          gap: 10px;
        }

        .bz-shs-progress-scale {
          display: grid;
          align-items: start;
          gap: 6px;
        }

        .bz-shs-progress-sounding {
          position: relative;
          display: block;
          min-height: 12px;
        }

        .bz-shs-progress-sounding::before,
        .bz-shs-progress-sounding::after {
          content: "";
          position: absolute;
          box-sizing: border-box;
          transition:
            background-color 220ms ease-out,
            height 220ms ease-out,
            top 220ms ease-out;
        }

        .bz-shs-progress-sounding::before {
          left: 0;
          right: 0;
          top: 4px;
          border-radius: 999px;
        }

        .bz-shs-progress-sounding[data-state="complete"]::before,
        .bz-shs-progress-sounding[data-state="current"]::before {
          top: 3px;
          height: 4px;
          background: var(--accent-funnel);
        }

        /* Done is ink, "you are here" is merah: the red marks one place per
         * viewport (R3) instead of flooding the rail as answers pile up. */
        .bz-shs-progress-sounding[data-state="complete"]::before {
          background: var(--text-primary);
        }

        .bz-shs-progress-sounding[data-state="pending"]::before {
          height: 2px;
          background: var(--bz-shs-progress-track);
        }

        .bz-shs-progress-sounding[data-state="current"]::after {
          right: -2px;
          top: 0;
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: var(--accent-funnel);
          box-shadow: 0 0 0 3px var(--surface-base);
        }

        .bz-shs-progress-name {
          display: none;
        }

        .bz-shs-progress-meta {
          display: flex;
          align-items: baseline;
          gap: 10px;
        }

        .bz-shs-progress-meta p {
          margin: 0;
          font-size: 0.8125rem;
          line-height: 1.3;
        }

        .bz-shs-progress-count {
          color: var(--text-secondary);
          font-variant-numeric: tabular-nums;
          letter-spacing: 0.02em;
        }

        .bz-shs-progress-current {
          color: var(--text-primary);
          font-weight: 600;
        }

        .bz-shs-progress-current::before {
          content: "·";
          margin-right: 10px;
          color: var(--text-secondary);
          font-weight: 400;
        }

        @media (min-width: 720px) {
          .bz-shs-progress-name {
            display: block;
            padding-top: 18px;
            font-size: 0.8125rem;
            line-height: 1.25;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .bz-shs-progress-sounding[data-state="current"] .bz-shs-progress-name {
            color: var(--text-primary);
            font-weight: 600;
          }
          .bz-shs-progress-rail:has(.bz-shs-progress-name) .bz-shs-progress-current {
            display: none;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .bz-shs-progress-sounding::before,
          .bz-shs-progress-sounding::after {
            transition: none !important;
          }
        }
      `}</style>
    </div>
  );
}

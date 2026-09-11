"use client";

export interface ProgressRailProps {
  /** 1-indexed current step number. */
  step: number;
  /** Total step count for the CURRENT branch — adapts as answers narrow
   *  down the wizard sequence (spec §4: "M adapts to branch"). */
  total: number;
}

type ProgressState = "complete" | "current" | "pending";

/** Bathymetric progress scale + "Step N of M" label. Pure/presentational —
 *  StudioApp owns all step-sequencing logic. */
export function ProgressRail({ step, total }: ProgressRailProps) {
  const safeTotal = Number.isFinite(total) ? Math.max(1, Math.trunc(total)) : 1;
  const safeStep = Number.isFinite(step)
    ? Math.min(safeTotal, Math.max(1, Math.trunc(step)))
    : 1;

  // The displayed checkpoint is already reached, so step 1 of 6 is one-sixth complete.
  const soundings = Array.from({ length: safeTotal }, (_, index) => {
    const sounding = index + 1;
    const state: ProgressState =
      sounding < safeStep
        ? "complete"
        : sounding === safeStep
          ? "current"
          : "pending";

    return { sounding, state };
  });

  return (
    <div className="bz-shs-progress-rail">
      <div
        aria-label="Interview progress"
        aria-valuemax={safeTotal}
        aria-valuemin={0}
        aria-valuenow={safeStep}
        className="bz-shs-progress-scale"
        role="progressbar"
        style={{
          gridTemplateColumns: `repeat(${safeTotal}, minmax(0, 1fr))`,
        }}
      >
        {soundings.map(({ sounding, state }) => (
          <span
            aria-hidden="true"
            className="bz-shs-progress-sounding"
            data-progress-reached={state !== "pending" ? "true" : "false"}
            data-state={state}
            key={sounding}
          />
        ))}
      </div>
      <p
        aria-hidden="true"
        style={{
          margin: 0,
          fontSize: "var(--text-xs, 0.72rem)",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        Step {safeStep} of {safeTotal}
      </p>
      <style>{`
        .bz-shs-progress-rail {
          --bz-shs-progress-pending: color-mix(
            in srgb,
            var(--text-primary) 46%,
            transparent
          );
          display: grid;
          gap: var(--space-1, 0.3rem);
        }

        .bz-shs-progress-scale {
          display: grid;
          align-items: end;
          gap: clamp(0.3rem, 0.8vw, 0.55rem);
          min-height: 16px;
        }

        .bz-shs-progress-sounding {
          position: relative;
          display: block;
          height: 16px;
        }

        .bz-shs-progress-sounding::before,
        .bz-shs-progress-sounding::after {
          content: "";
          position: absolute;
          right: 0;
          bottom: 0;
          box-sizing: border-box;
          transition:
            border-color 220ms ease-out,
            background-color 220ms ease-out,
            height 220ms ease-out;
        }

        .bz-shs-progress-sounding::before {
          left: 0;
        }

        .bz-shs-progress-sounding[data-state="complete"]::before,
        .bz-shs-progress-sounding[data-state="current"]::before {
          border-top: 3px solid var(--accent-funnel);
        }

        .bz-shs-progress-sounding[data-state="complete"]::after {
          width: 3px;
          height: 9px;
          background: var(--accent-funnel);
        }

        .bz-shs-progress-sounding[data-state="current"]::after {
          width: 4px;
          height: 16px;
          background: var(--accent-funnel);
        }

        .bz-shs-progress-sounding[data-state="pending"]::before {
          border-top: 3px dashed var(--bz-shs-progress-pending);
        }

        .bz-shs-progress-sounding[data-state="pending"]::after {
          width: 7px;
          height: 9px;
          border: 2px solid var(--bz-shs-progress-pending);
          background: var(--surface-base-solid, var(--surface-deep));
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

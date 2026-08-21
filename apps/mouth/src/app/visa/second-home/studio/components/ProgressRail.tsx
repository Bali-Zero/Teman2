"use client";

export interface ProgressRailProps {
  /** 1-indexed current step number. */
  step: number;
  /** Total step count for the CURRENT branch — adapts as answers narrow
   *  down the wizard sequence (spec §4: "M adapts to branch"). */
  total: number;
}

/** Hairline progress bar + "Step N of M" label. Pure/presentational —
 *  StudioApp owns all step-sequencing logic. */
export function ProgressRail({ step, total }: ProgressRailProps) {
  const pct = total > 0 ? Math.min(100, Math.max(0, (step / total) * 100)) : 0;

  return (
    <div style={{ display: "grid", gap: "var(--space-1, 0.3rem)" }}>
      <div
        role="progressbar"
        aria-valuenow={step}
        aria-valuemin={1}
        aria-valuemax={total}
        style={{
          height: 4,
          borderRadius: 4,
          background: "var(--color-border-subtle)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: "var(--accent-funnel)",
            transition: "width 220ms ease-out",
          }}
        />
      </div>
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-xs, 0.72rem)",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "var(--color-text-muted)",
        }}
      >
        Step {step} of {total}
      </p>
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          [role="progressbar"] > div { transition: none !important; }
        }
      `}</style>
    </div>
  );
}

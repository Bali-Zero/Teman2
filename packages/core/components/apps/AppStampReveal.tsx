"use client";

import type { FC } from "react";

export interface AppStampRevealProps {
  code: string;
  variant?: "rotate" | "flat";
  /** Optional aria-label override. Defaults to "Visa code <code>". */
  ariaLabel?: string;
}

/**
 * Iconic stamp reveal for the Visa Check result pages. Renders the visa
 * code in serif italic with a red double-border, rotated -4° by default,
 * with an "ink press" animation on mount (scale 1.15 → 1, 400ms overshoot).
 *
 * Respects prefers-reduced-motion: no scale, instant fade.
 *
 * Spec: docs/superpowers/specs/2026-04-20-visa-check-ui-design.md §5 Result page
 */
export const AppStampReveal: FC<AppStampRevealProps> = ({
  code,
  variant = "rotate",
  ariaLabel,
}) => {
  const transform = variant === "rotate" ? "rotate(-4deg)" : "none";
  // Suffix keyframe names by variant so two stamps with different variants
  // on the same page don't collide (both would be named bz-ink-press otherwise,
  // and the second declaration would overwrite the first globally).
  const keyframeName = `bz-ink-press-${variant}`;
  const keyframeNameRm = `bz-ink-press-rm-${variant}`;
  return (
    <div
      data-testid="bz-stamp"
      role="img"
      aria-label={ariaLabel ?? `Visa code ${code}`}
      style={{
        display: "inline-block",
        fontFamily: "var(--font-serif, Georgia, 'Times New Roman', serif)",
        fontStyle: "italic",
        fontSize: "clamp(2.2rem, 6vw, 3.2rem)",
        color: "var(--accent-funnel, #ff3344)",
        border: "3px double color-mix(in srgb, var(--accent-funnel) 60%, transparent)",
        padding: "0.4rem 1rem",
        transform,
        boxShadow: "0 0 20px color-mix(in srgb, var(--accent-funnel) 15%, transparent)",
        animation: `${keyframeName} var(--motion-duration-slow, 400ms) var(--motion-curve-reveal, cubic-bezier(0.5, 0, 0.3, 1.2)) both`,
      }}
    >
      <style>{`
        @keyframes ${keyframeName} {
          0%   { transform: ${transform} scale(1.15); opacity: 0; }
          100% { transform: ${transform} scale(1); opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          [data-testid="bz-stamp"] {
            animation: ${keyframeNameRm} var(--motion-duration-base, 250ms) linear both !important;
          }
          @keyframes ${keyframeNameRm} {
            0%   { opacity: 0; }
            100% { opacity: 1; }
          }
        }
      `}</style>
      {code}
    </div>
  );
};

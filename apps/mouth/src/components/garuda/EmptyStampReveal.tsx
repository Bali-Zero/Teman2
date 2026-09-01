"use client";

import type { FC } from "react";

export interface EmptyStampRevealProps {
  /** Optional aria-label override. Defaults to "No stamp — this application was not approved". */
  ariaLabel?: string;
}

/**
 * GARUDA VOA — the DECLINE stamp (owner decision 5, "Concept A — The Stamp").
 *
 * Extends the ink-stamp visual language already proven on Visa Match/Clock
 * (`AppStampReveal`: red double-border, serif italic, ink-press animation) to
 * its opposite case. An ACCEPT gets the ink pressed down — `AppStampReveal`
 * with the price/deadline as its code. A DECLINE gets this: the SAME frame,
 * dashed instead of solid, muted instead of red, and empty — no code, no ink.
 *
 * Zero's ask (2026-08-24 ratification of owner decision 5) was to see this
 * exact shape on a real phone before anything else got built: "if the NO
 * feels like a door closing, the concept has failed." The empty frame is the
 * answer to that test — it says "nothing was stamped here", not "denied".
 * The educational copy that mirrors the customer's answer and names the
 * alternative (constraint 5b) lives beside this component, never inside it —
 * the stamp itself stays wordless on purpose.
 */
export const EmptyStampReveal: FC<EmptyStampRevealProps> = ({ ariaLabel }) => {
  const transform = "rotate(-4deg)";
  return (
    <div
      data-testid="bz-empty-stamp"
      role="img"
      aria-label={ariaLabel ?? "No stamp — this application was not approved"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: "min(80vw, 260px)",
        minHeight: "clamp(3.6rem, 9vw, 5rem)",
        fontFamily: "var(--font-serif, Georgia, 'Times New Roman', serif)",
        fontStyle: "italic",
        fontSize: "clamp(1rem, 3.2vw, 1.3rem)",
        color: "var(--color-text-muted, rgba(255, 255, 255, 0.45))",
        border:
          "3px dashed var(--color-border-subtle, rgba(255, 255, 255, 0.25))",
        borderRadius: 4,
        padding: "0.4rem 1rem",
        transform,
        opacity: 0.85,
        animation:
          "bz-empty-stamp-fade var(--motion-duration-base, 250ms) linear both",
      }}
    >
      <style>{`
        @keyframes bz-empty-stamp-fade {
          0%   { opacity: 0; }
          100% { opacity: 0.85; }
        }
        @media (prefers-reduced-motion: reduce) {
          [data-testid="bz-empty-stamp"] { animation: none !important; }
        }
      `}</style>
      <span data-testid="bz-empty-stamp-label">— no stamp —</span>
    </div>
  );
};

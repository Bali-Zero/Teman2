"use client";

import type { Ref } from "react";
import { getCopy } from "@/lib/secondhome-studio/copy";
import type { Verdict, VerdictBand } from "@/lib/secondhome-studio/types";

export interface VerdictPanelProps {
  verdict: Verdict;
  /** Forwarded to the `<h1>` fit-check heading so StudioApp can move focus
   *  to it on the question-wizard -> verdict transition (P2-3) — the
   *  heading carries `tabIndex={-1}` so a non-interactive element can
   *  still be a programmatic focus target. */
  headingRef?: Ref<HTMLHeadingElement>;
}

interface BandStyle {
  borderColor: string;
  borderWidth: number;
  icon: React.ReactNode;
  background: string;
}

const CHECK_ICON = (
  <svg
    aria-hidden="true"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

const INFO_ICON = (
  <svg
    aria-hidden="true"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4" />
    <path d="M12 8h.01" />
  </svg>
);

const WARNING_ICON = (
  <svg
    aria-hidden="true"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </svg>
);

const CLOSE_ICON = (
  <svg
    aria-hidden="true"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
);

const BAND_STYLES: Record<VerdictBand, BandStyle> = {
  strong_fit: {
    borderColor: "var(--state-success)",
    borderWidth: 3,
    icon: CHECK_ICON,
    background: "color-mix(in srgb, var(--state-success) 6%, transparent)",
  },
  likely_fit: {
    borderColor: "var(--state-info)",
    borderWidth: 2,
    icon: INFO_ICON,
    background: "color-mix(in srgb, var(--state-info) 6%, transparent)",
  },
  edge_case: {
    borderColor: "var(--state-warning)",
    borderWidth: 2,
    icon: WARNING_ICON,
    background: "color-mix(in srgb, var(--state-warning) 6%, transparent)",
  },
  not_eligible: {
    // Deliberately neutral rather than --state-danger: a clear, respectful
    // "no" for a 55+ risk-averse audience. The signal is carried by the
    // icon shape and border weight in addition to the muted tone.
    borderColor: "var(--text-secondary)",
    borderWidth: 2,
    icon: CLOSE_ICON,
    background: "color-mix(in srgb, var(--text-secondary) 8%, transparent)",
  },
};

/** Renders the fit-check result: band heading/body (verbatim from copy.ts,
 *  which guarantees "the final decision rests with Imigrasi" is present),
 *  the reason list, and the human-review disclosure when present.
 *  NEVER renders a numeric score — spec §0 hard constraint. */
export function VerdictPanel({ verdict, headingRef }: VerdictPanelProps) {
  const heading = getCopy(`verdict.bands.${verdict.band}.heading`);
  const body = getCopy(`verdict.bands.${verdict.band}.body`);
  const style = BAND_STYLES[verdict.band];

  return (
    <section
      data-verdict-band={verdict.band}
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: style.background,
        border: `${style.borderWidth}px solid ${style.borderColor}`,
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
        fontVariantNumeric: "tabular-nums",
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: "0.7rem",
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          opacity: 0.6,
          color: "var(--color-text-muted)",
        }}
      >
        Your fit-check result
      </p>
      <div
        aria-hidden="true"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 44,
          height: 44,
          borderRadius: "50%",
          color: style.borderColor,
          background: "color-mix(in srgb, currentColor 10%, transparent)",
        }}
      >
        {style.icon}
      </div>
      <h1
        ref={headingRef}
        tabIndex={-1}
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          // S13 verdict-crown: this is now the page's SOLE <h1> on the
          // verdict stage (StudioApp's masthead recedes to a presentational
          // label there) — raised from clamp(2.2rem,6vw,3.5rem)/56px so it
          // reads as the page's crown. Capped at 3.75rem/60px, inside the
          // 46-64px "whispered authority" band (never the masthead's 105px)
          // per spec.
          fontSize: "clamp(2.4rem, 6.5vw, 3.75rem)",
          lineHeight: 1.1,
          color: "var(--text-primary)",
        }}
      >
        {heading}
      </h1>
      <p style={{ margin: 0, lineHeight: 1.7, color: "var(--text-primary)" }}>
        {body}
      </p>
      {verdict.product ? (
        <p
          style={{
            margin: 0,
            fontSize: "var(--text-sm, 0.88rem)",
            color: "var(--color-text-muted)",
          }}
        >
          Matching product: <strong>{verdict.product}</strong>
        </p>
      ) : null}
      {verdict.reasons.length > 0 ? (
        <ul
          style={{
            margin: 0,
            paddingLeft: "1.2rem",
            display: "grid",
            gap: "var(--space-2, 0.5rem)",
            color: "var(--text-primary)",
          }}
        >
          {verdict.reasons.map((key) => (
            <li key={key}>{getCopy(key)}</li>
          ))}
        </ul>
      ) : null}
      {verdict.humanReviewNote ? (
        <p
          role="note"
          style={{
            margin: 0,
            padding: "var(--space-2, 0.5rem)",
            borderLeft: `3px solid ${style.borderColor}`,
            fontSize: "var(--text-sm, 0.88rem)",
            color: "var(--text-primary)",
          }}
        >
          {getCopy(verdict.humanReviewNote)}
        </p>
      ) : null}
    </section>
  );
}

"use client";

import type { Ref } from "react";
import { getCopy } from "@/lib/secondhome-studio/copy";
import type { Verdict, VerdictBand } from "@/lib/secondhome-studio/types";
import { BAND_TONES, glassBackground } from "../room/bandTones";

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
    borderColor: BAND_TONES.strong_fit,
    borderWidth: 3,
    icon: CHECK_ICON,
    background: glassBackground("strong_fit"),
  },
  likely_fit: {
    borderColor: BAND_TONES.likely_fit,
    borderWidth: 2,
    icon: INFO_ICON,
    background: glassBackground("likely_fit"),
  },
  edge_case: {
    borderColor: BAND_TONES.edge_case,
    borderWidth: 2,
    icon: WARNING_ICON,
    background: glassBackground("edge_case"),
  },
  not_eligible: {
    // Deliberately neutral rather than --state-danger: a clear, respectful
    // "no" for a 55+ risk-averse audience. The signal is carried by the
    // icon shape and border weight in addition to the muted tone.
    borderColor: BAND_TONES.not_eligible,
    borderWidth: 2,
    icon: CLOSE_ICON,
    background: glassBackground("not_eligible"),
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
      className="bz-shs-window"
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        // The glass over raised paper, so the band's light reads the same
        // whatever surface the window hangs on (the desk is wash).
        background: `linear-gradient(${style.background}, ${style.background}), var(--surface-raised, transparent)`,
        border: `${style.borderWidth}px solid ${style.borderColor}`,
        // The window (BRIEF-v2 §3.2): a flat R19 frame; the band is its light.
        borderRadius: 2,
        padding: "var(--space-4, 1.5rem)",
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {/* Three panes of glass lit by the band — decoration only; the band's
          words and icon below carry the meaning. */}
      <div
        aria-hidden="true"
        className="bz-shs-window-panes"
        style={{ color: style.borderColor }}
      >
        <span />
        <span />
        <span />
      </div>
      <p
        style={{
          margin: 0,
          fontSize: "0.7rem",
          fontWeight: 700,
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          // No opacity: muted ink at 0.6 composited under 4.5:1 on paper.
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
        className="bz-shs-window-title"
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          // S13 verdict-crown: this is now the page's SOLE <h1> on the
          // verdict stage (StudioApp's masthead recedes to a presentational
          // label there) — raised from clamp(2.2rem,6vw,3.5rem)/56px so it
          // reads as the page's crown. Capped at 3.75rem/60px, inside the
          // 46-64px "whispered authority" band (never the masthead's 105px)
          // per spec.
          // R19 room: the window sits in the desk column, not full width.
          fontSize: "clamp(2rem, 3.6vw, 3rem)",
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

"use client";

import type { Ref } from "react";
import { getCopy } from "@/lib/secondhome-studio/copy";
import type { Verdict } from "@/lib/secondhome-studio/types";

export interface VerdictPanelProps {
  verdict: Verdict;
  /** Forwarded to the `<h1>` fit-check heading so StudioApp can move focus
   *  to it on the question-wizard -> verdict transition (P2-3) — the
   *  heading carries `tabIndex={-1}` so a non-interactive element can
   *  still be a programmatic focus target. */
  headingRef?: Ref<HTMLHeadingElement>;
}

/** Renders the fit-check result: band heading/body (verbatim from copy.ts,
 *  which guarantees "the final decision rests with Imigrasi" is present),
 *  the reason list, and the human-review disclosure when present.
 *  NEVER renders a numeric score — spec §0 hard constraint. */
export function VerdictPanel({ verdict, headingRef }: VerdictPanelProps) {
  const heading = getCopy(`verdict.bands.${verdict.band}.heading`);
  const body = getCopy(`verdict.bands.${verdict.band}.body`);

  return (
    <section
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: "2px solid var(--accent-funnel)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
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
      <h1
        ref={headingRef}
        tabIndex={-1}
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.6rem, 4vw, 2.2rem)",
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
            borderLeft: "3px solid var(--accent-funnel)",
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

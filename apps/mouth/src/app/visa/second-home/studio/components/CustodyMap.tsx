"use client";

import { getCopy } from "@/lib/secondhome-studio/copy";

const STEPS = ["step1", "step2", "step3"] as const;

/** Static 3-step custody explainer (spec §5). No yield/return figures, no
 *  LPS mention — copy.ts's own forbidden-claims sweep enforces this across
 *  every string this component reads. */
export function CustodyMap() {
  return (
    <section
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: "1px solid var(--color-border-subtle)",
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
        Custody
      </p>
      <h2
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.2rem, 3vw, 1.5rem)",
          color: "var(--text-primary)",
        }}
      >
        {getCopy("custody.eyebrow")}
      </h2>
      <p style={{ margin: 0, lineHeight: 1.6, color: "var(--text-primary)" }}>
        {getCopy("custody.intro")}
      </p>
      <ol
        style={{
          margin: 0,
          padding: 0,
          listStyle: "none",
          display: "grid",
          gap: "var(--space-3, 1rem)",
        }}
      >
        {STEPS.map((step, i) => (
          <li
            key={step}
            style={{ display: "grid", gap: "var(--space-1, 0.3rem)" }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-2, 0.5rem)",
              }}
            >
              {/* Step badge — matches the timeline's rounded, bordered
               *  "owner chip" language (TimelineView.tsx) instead of a bare
               *  numeral, aria-hidden since the number is decorative
               *  (the step order is already conveyed by the <ol>). */}
              <span
                aria-hidden
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  border: "1.5px solid var(--accent-funnel)",
                  fontFamily: "var(--font-serif, Georgia, serif)",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "var(--accent-funnel-text, var(--accent-funnel))",
                }}
              >
                {i + 1}
              </span>
              <strong style={{ color: "var(--text-primary)" }}>
                {getCopy(`custody.steps.${step}.title`)}
              </strong>
            </div>
            <p
              style={{
                margin: 0,
                marginLeft: "1.3rem",
                color: "var(--color-text-muted)",
                lineHeight: 1.6,
              }}
            >
              {getCopy(`custody.steps.${step}.body`)}
            </p>
          </li>
        ))}
      </ol>
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.82rem)",
          color: "var(--color-text-muted)",
          fontStyle: "italic",
        }}
      >
        {getCopy("custody.disclaimer")}
      </p>
    </section>
  );
}

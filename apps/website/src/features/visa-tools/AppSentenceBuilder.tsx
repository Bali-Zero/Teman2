"use client";

import type { FC, ReactNode } from "react";

export interface AppSentenceBuilderProps {
  /** e.g. "I entered on {entry} with a {visa} visa." */
  template: string;
  /** Map of {slotName} → ReactNode. Unknown slots are left literal. */
  fields: Record<string, ReactNode>;
}

/**
 * Renders an editorial sentence with inline form fields in place of
 * {slotName} placeholders. Fields stack vertically on narrow viewports
 * (the connecting words remain readable — this is enforced purely by the
 * inline-block + wrap behavior, no JS needed).
 *
 * Spec: docs/superpowers/specs/2026-04-20-visa-check-ui-design.md §2 Clock form
 */
export const AppSentenceBuilder: FC<AppSentenceBuilderProps> = ({
  template,
  fields,
}) => {
  // Tokenize on {slot} boundaries, preserving the literals.
  const parts = template.split(/(\{[a-zA-Z_][a-zA-Z0-9_]*\})/g);
  return (
    <p
      style={{
        fontSize: "clamp(1.1rem, 2.6vw, 1.3rem)",
        lineHeight: 1.9,
        margin: 0,
        color: "var(--text-primary, rgba(255, 255, 255, 0.96))",
        fontFamily: "var(--font-serif, Georgia, 'Times New Roman', serif)",
      }}
    >
      {parts.map((part, i) => {
        const match = part.match(/^\{([a-zA-Z_][a-zA-Z0-9_]*)\}$/);
        if (!match) return <span key={i}>{part}</span>;
        const slot = match[1];
        if (slot in fields) {
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                margin: "0 0.35em",
                verticalAlign: "middle",
              }}
            >
              {fields[slot]}
            </span>
          );
        }
        // Unknown slot — leave literal so the gap is visible in dev.
        return <span key={i}>{part}</span>;
      })}
    </p>
  );
};

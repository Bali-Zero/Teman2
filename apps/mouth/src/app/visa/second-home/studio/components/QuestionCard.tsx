"use client";

import type { ReactNode } from "react";

export interface QuestionCardProps {
  heading: string;
  body: string;
  /** "Why we ask" aside body — collapsed by default, always keyboard
   *  reachable via the native <details>/<summary> disclosure pattern. */
  why: string;
  children: ReactNode;
}

/** Chrome wrapper for one wizard screen: heading/body (from copy.ts),
 *  a collapsible "Why we ask" aside, and a slot for the answer UI (option
 *  cards, or a custom control set like the family step). */
export function QuestionCard({
  heading,
  body,
  why,
  children,
}: QuestionCardProps) {
  return (
    <div
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
      }}
    >
      <h2
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.25rem, 3vw, 1.6rem)",
          color: "var(--text-primary)",
        }}
      >
        {heading}
      </h2>
      <p style={{ margin: 0, lineHeight: 1.6, color: "var(--text-primary)" }}>
        {body}
      </p>
      <details style={{ fontSize: "var(--text-sm, 0.88rem)" }}>
        <summary
          style={{
            cursor: "pointer",
            color: "var(--color-text-muted)",
            fontWeight: 600,
          }}
        >
          Why we ask
        </summary>
        <p
          style={{
            margin: "var(--space-2, 0.5rem) 0 0",
            color: "var(--color-text-muted)",
            lineHeight: 1.5,
          }}
        >
          {why}
        </p>
      </details>
      <div style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}>
        {children}
      </div>
    </div>
  );
}

export interface OptionButtonProps {
  label: string;
  selected: boolean;
  onSelect: () => void;
}

/** Large, keyboard-focusable option card. Never strips the native focus
 *  ring (accessibility — spec §0 "visible focus"). */
export function OptionButton({ label, selected, onSelect }: OptionButtonProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      style={{
        padding: "var(--space-3, 0.85rem) var(--space-4, 1.1rem)",
        borderRadius: 8,
        border: selected
          ? "2px solid var(--accent-funnel)"
          : "1px solid var(--color-border-subtle)",
        background: selected ? "var(--surface-base)" : "transparent",
        color: "var(--text-primary)",
        textAlign: "left",
        cursor: "pointer",
        minHeight: 44,
        fontSize: "1rem",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  );
}

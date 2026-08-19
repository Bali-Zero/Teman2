"use client";

import { useId, type ReactNode, type Ref } from "react";

export interface QuestionCardProps {
  heading: string;
  body: string;
  /** "Why we ask" aside body — collapsed by default, always keyboard
   *  reachable via the native <details>/<summary> disclosure pattern. */
  why: string;
  /** Single-select answer options (P2-4): rendered inside a
   *  `role="radiogroup"` container, `aria-labelledby` the heading — pass
   *  `<OptionButton variant="radio" .../>` elements. Omit for a
   *  multi-select step (family) — those keep the plain toggle-button
   *  markup via `children` instead. */
  options?: ReactNode;
  /** Forwarded to the stage `<h2>` so the caller can move focus to it on
   *  step transitions (P2-3) — the heading carries `tabIndex={-1}` so a
   *  non-interactive element can still be a programmatic focus target. */
  headingRef?: Ref<HTMLHeadingElement>;
  children: ReactNode;
}

/** Chrome wrapper for one wizard screen: heading/body (from copy.ts),
 *  a collapsible "Why we ask" aside, an optional radiogroup-wrapped
 *  options slot, and a slot for anything else (option cards, a custom
 *  control set like the family step, and/or the Back/Continue nav row). */
export function QuestionCard({
  heading,
  body,
  why,
  options,
  headingRef,
  children,
}: QuestionCardProps) {
  const headingId = useId();

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
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
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
      {options ? (
        <div
          role="radiogroup"
          aria-labelledby={headingId}
          style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}
        >
          {options}
        </div>
      ) : null}
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
  /** "radio" (P2-4): single-select question steps — renders `role="radio"`
   *  + `aria-checked`, intended for use inside a `role="radiogroup"`
   *  container. Default keeps the original plain toggle-button semantics
   *  (`aria-pressed`) used by the family multi-select step, where more
   *  than one option can be true at once.
   *
   *  Arrow-key roving-tabindex movement between radio options is left as
   *  a future enhancement — Tab-order navigation between options still
   *  works today; only the announced role/state changed here. */
  variant?: "radio" | "toggle";
}

/** Large, keyboard-focusable option card. Never strips the native focus
 *  ring (accessibility — spec §0 "visible focus"). */
export function OptionButton({
  label,
  selected,
  onSelect,
  variant = "toggle",
}: OptionButtonProps) {
  const isRadio = variant === "radio";
  return (
    <button
      type="button"
      onClick={onSelect}
      role={isRadio ? "radio" : undefined}
      aria-checked={isRadio ? selected : undefined}
      aria-pressed={isRadio ? undefined : selected}
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

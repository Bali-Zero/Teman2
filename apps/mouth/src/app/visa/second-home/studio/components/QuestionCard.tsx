"use client";

import { useId, type ReactNode, type Ref } from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronRight } from "lucide-react";

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
      <details
        className="bz-shs-why"
        style={{ fontSize: "var(--text-sm, 0.88rem)" }}
      >
        <summary
          className="bz-shs-why-summary"
          style={{
            cursor: "pointer",
            color: "var(--color-text-muted)",
            fontWeight: 600,
            listStyle: "none",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-1, 0.35rem)",
          }}
        >
          <ChevronRight
            size={14}
            aria-hidden
            className="bz-shs-why-chevron"
            style={{ flexShrink: 0 }}
          />
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
      {/* Single instance per render (only one question stage is ever
       *  mounted at a time) — matches the local-<style> pattern already
       *  used by ProgressRail/MemoPreview. Transitions here are already
       *  covered by StudioApp's `.bz-shs-layout * { transition: none }`
       *  reduced-motion rule, since QuestionCard only ever renders inside
       *  that container — no separate media query needed. */}
      <style>{`
        .bz-shs-why-summary::-webkit-details-marker {
          display: none;
        }
        .bz-shs-why-chevron {
          transition: transform 150ms ease-out;
        }
        .bz-shs-why[open] > .bz-shs-why-summary .bz-shs-why-chevron {
          transform: rotate(90deg);
        }
        /* OptionButton (P2 design pass): border/background driven by the
         * data-selected attribute rather than inline styles, so :hover can
         * actually take effect — an inline style attribute always beats a
         * stylesheet rule regardless of pseudo-class, so a hover rule
         * targeting a JS-computed inline border/background would silently
         * never apply. */
        .bz-shs-option {
          border: 1px solid var(--color-border-subtle);
          background: transparent;
          transition:
            border-color 150ms ease-out,
            background-color 150ms ease-out;
        }
        .bz-shs-option:hover {
          border-color: var(--accent-funnel);
          background: color-mix(in srgb, var(--accent-funnel) 6%, transparent);
        }
        .bz-shs-option[data-selected="true"] {
          border: 2px solid var(--accent-funnel);
          background: color-mix(in srgb, var(--accent-funnel) 12%, transparent);
        }
        .bz-shs-option[data-selected="true"]:hover {
          background: color-mix(in srgb, var(--accent-funnel) 16%, transparent);
        }
      `}</style>
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
  /** Optional leading icon for route-style options. Rendered `aria-hidden`
   *  because the textual label already carries the meaning. */
  icon?: LucideIcon;
}

/** Decorative leading affordance for a radio-variant option: an empty ring
 *  that fills with an accent dot when selected. `aria-hidden` — the radio
 *  semantics live on the parent `role="radio"`/`aria-checked` button, this
 *  is purely visual and contributes nothing to its accessible name. */
function RadioAffordance({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        width: 20,
        height: 20,
        borderRadius: "50%",
        border: selected
          ? "2px solid var(--accent-funnel)"
          : "1.5px solid var(--color-border-subtle)",
      }}
    >
      {selected ? (
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: "var(--accent-funnel)",
          }}
        />
      ) : null}
    </span>
  );
}

/** Decorative leading affordance for a toggle-variant option (the family
 *  multi-select step): a small square that fills with a check mark when
 *  selected. `aria-hidden` for the same reason as RadioAffordance. */
function CheckAffordance({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        width: 20,
        height: 20,
        borderRadius: 5,
        border: selected
          ? "2px solid var(--accent-funnel)"
          : "1.5px solid var(--color-border-subtle)",
        background: selected ? "var(--accent-funnel)" : "transparent",
        color: "var(--text-on-accent, #fff)",
        fontSize: 13,
        lineHeight: 1,
      }}
    >
      {selected ? "✓" : null}
    </span>
  );
}

/** Large, keyboard-focusable option card. Never strips the native focus
 *  ring (accessibility — spec §0 "visible focus"). Border/background are
 *  driven by the `bz-shs-option` CSS class + `data-selected` attribute
 *  (see QuestionCard's local <style>) rather than inline styles, so hover
 *  can layer on top; the leading radio/check affordance is decorative
 *  (`aria-hidden`) — the real selected-state semantics stay on
 *  `role`/`aria-checked`/`aria-pressed`, unchanged. */
export function OptionButton({
  label,
  selected,
  onSelect,
  variant = "toggle",
  icon: Icon,
}: OptionButtonProps) {
  const isRadio = variant === "radio";
  return (
    <button
      type="button"
      onClick={onSelect}
      role={isRadio ? "radio" : undefined}
      aria-checked={isRadio ? selected : undefined}
      aria-pressed={isRadio ? undefined : selected}
      className="bz-shs-option"
      data-selected={selected ? "true" : "false"}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3, 0.75rem)",
        padding: "var(--space-3, 0.85rem) var(--space-4, 1.1rem)",
        borderRadius: 8,
        color: "var(--text-primary)",
        textAlign: "left",
        cursor: "pointer",
        minHeight: 44,
        fontSize: "1rem",
        fontFamily: "inherit",
      }}
    >
      {isRadio ? (
        <RadioAffordance selected={selected} />
      ) : (
        <CheckAffordance selected={selected} />
      )}
      {Icon ? (
        <Icon
          size={18}
          strokeWidth={1.5}
          aria-hidden
          style={{
            flexShrink: 0,
            color: "var(--color-text-muted)",
          }}
        />
      ) : null}
      <span>{label}</span>
    </button>
  );
}

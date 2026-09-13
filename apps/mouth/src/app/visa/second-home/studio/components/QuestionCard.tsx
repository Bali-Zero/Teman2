"use client";

import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from "react";
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

function handleRadioGroupKeyDown(event: KeyboardEvent<HTMLDivElement>) {
  const target = event.target;
  if (!(target instanceof Element)) return;

  const currentRadio = target.closest<HTMLButtonElement>('[role="radio"]');
  if (!currentRadio || !event.currentTarget.contains(currentRadio)) return;

  const radios = Array.from(
    event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]'),
  );
  const currentIndex = radios.indexOf(currentRadio);
  if (currentIndex < 0 || radios.length === 0) return;

  let nextIndex: number;
  switch (event.key) {
    case "ArrowDown":
    case "ArrowRight":
      nextIndex = (currentIndex + 1) % radios.length;
      break;
    case "ArrowUp":
    case "ArrowLeft":
      nextIndex = (currentIndex - 1 + radios.length) % radios.length;
      break;
    case "Home":
      nextIndex = 0;
      break;
    case "End":
      nextIndex = radios.length - 1;
      break;
    default:
      return;
  }

  event.preventDefault();
  const nextRadio = radios[nextIndex];
  nextRadio.focus();
  nextRadio.click();
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
  const optionNodes = Children.toArray(options);
  const radioIndexes = optionNodes.flatMap((option, index) =>
    isValidElement<OptionButtonProps>(option) &&
    option.type === OptionButton &&
    option.props.variant === "radio"
      ? [index]
      : [],
  );
  const selectedRadioIndex = radioIndexes.find((index) => {
    const option = optionNodes[index];
    return isValidElement<OptionButtonProps>(option) && option.props.selected;
  });
  const tabbableRadioIndex = selectedRadioIndex ?? radioIndexes[0];
  const radioOptions = optionNodes.map((option, index) =>
    isValidElement<OptionButtonProps>(option) &&
    option.type === OptionButton &&
    option.props.variant === "radio"
      ? cloneElement(option, {
          tabIndex: index === tabbableRadioIndex ? 0 : -1,
        })
      : option,
  );

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
          // R4 §3: Cormorant is display-only and never below 24px — under that,
          // low-DPI Android antialiasing shreds the serif.
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.5rem, 3vw, 1.6rem)",
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
          onKeyDown={handleRadioGroupKeyDown}
          style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}
        >
          {radioOptions}
        </div>
      ) : null}
      <div style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}>
        {children}
      </div>
      {/* Single instance per render (only one question stage is ever
       *  mounted at a time) — matches the local-<style> pattern already
       *  used by ProgressRail/MemoPreview. */}
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
         * never apply.
         * WCAG 2.2 SC 1.4.11 (2026-09-01): this is the sole resting-state
         * boundary of every wizard option, and --color-border-subtle
         * composites to 1.21:1 on carta / 1.31:1 on white — the hairline is
         * decorative-only (merahPutihDayVars.ts's own comment says so) and
         * never the sole identifier of an interactive component. RadioAffordance
         * and CheckAffordance below already use --border-strong (3.64:1 on
         * carta / 3.94:1 on white) for the same reason; this outer boundary
         * now matches instead of undercutting them. */
        .bz-shs-option {
          border: 1px solid var(--border-strong);
          background: transparent;
          box-shadow: inset 0 0 0 0 transparent;
          transition:
            border-color 150ms ease-out,
            background-color 150ms ease-out,
            box-shadow 150ms ease-out;
        }
        .bz-shs-option:hover {
          border-color: var(--accent-funnel);
          background: color-mix(in srgb, var(--accent-funnel) 6%, transparent);
        }
        /* R4 §3/§4.5: the chosen option is an INK outline, never red. Red is
           allowed exactly two duties on this page — structure (the progress
           fill, brand marks) and action (the single primary CTA). Painting
           "chosen" in the same red is the three-meaning collision the identity
           law exists to remove, and it also made the selected option compete
           with the Continue button for the eye. Ink at 14.79:1 on carta is a
           stronger boundary than the red it replaces. */
        .bz-shs-option[data-selected="true"] {
          border-color: var(--text-primary);
          background: color-mix(in srgb, var(--text-primary) 6%, transparent);
          box-shadow: inset 0 0 0 2px var(--text-primary);
        }
        .bz-shs-option[data-selected="true"]:hover {
          background: color-mix(in srgb, var(--text-primary) 9%, transparent);
        }
        .bz-shs-option:focus-visible {
          outline: 3px solid var(--text-primary);
          outline-offset: 3px;
        }
        @media (prefers-reduced-motion: reduce) {
          .bz-shs-why-chevron,
          .bz-shs-option {
            transition: none !important;
          }
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
   *  The enclosing QuestionCard radiogroup owns roving tabindex and radio
   *  keyboard movement. */
  variant?: "radio" | "toggle";
  /** Optional leading icon for route-style options. Rendered `aria-hidden`
   *  because the textual label already carries the meaning. */
  icon?: LucideIcon;
  /** Injected by QuestionCard for radio variants. Toggle buttons deliberately
   *  omit this so each remains in the document's normal Tab order. */
  tabIndex?: 0 | -1;
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
        // R4 §3/§4.5: SELECTION IS NEVER RED. Red carries exactly two duties —
        // structure and action — and letting it also mean "chosen" is the
        // three-meaning collision the identity law exists to kill. Selected is
        // an INK outline; the unselected ring uses border-input (#7a8093,
        // 3.64:1 on carta), never the hairline (1.21:1), because this ring is
        // what identifies an interactive control (WCAG 2.2 SC 1.4.11).
        // The signal is not colour-alone either way: ring weight changes and
        // the inner mark appears.
        border: selected
          ? "2px solid var(--text-primary)"
          : "1.5px solid var(--border-strong)",
      }}
    >
      {selected ? (
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: "var(--text-primary)",
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
        // R4 §3/§4.5: selection is never red — ink box + white check. The
        // unselected boundary is border-input, not the decorative hairline.
        // White on ink measures 16.00:1; the check glyph is a second,
        // non-colour channel on top of the fill.
        border: selected
          ? "2px solid var(--text-primary)"
          : "1.5px solid var(--border-strong)",
        background: selected ? "var(--text-primary)" : "transparent",
        color: "#ffffff",
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
  tabIndex,
}: OptionButtonProps) {
  const isRadio = variant === "radio";
  return (
    <button
      type="button"
      onClick={onSelect}
      role={isRadio ? "radio" : undefined}
      aria-checked={isRadio ? selected : undefined}
      aria-pressed={isRadio ? undefined : selected}
      tabIndex={isRadio ? (tabIndex ?? 0) : undefined}
      className="bz-shs-option"
      data-selected={selected ? "true" : "false"}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3, 0.75rem)",
        padding: "var(--space-3, 0.85rem) var(--space-4, 1.1rem)",
        borderRadius: 12,
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

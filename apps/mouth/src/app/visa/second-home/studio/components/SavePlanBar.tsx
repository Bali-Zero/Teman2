"use client";

import { useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { getCopy } from "@/lib/secondhome-studio/copy";
import {
  encodePlanFragment,
  savePlan,
} from "@/lib/secondhome-studio/plan-codec";
import { relevantPlan } from "@/lib/secondhome-studio/sequence";
import type { PlanState } from "@/lib/secondhome-studio/types";

const STUDIO_PATH = "/visa/second-home/studio";

// Two-step destructive confirm (P0, 2026-08-24): how long the armed
// (confirming) state stays up before silently disarming, so the control is
// never left destructive indefinitely if the user walks away mid-decision.
// 5s splits the ~4-6s window this needs to sit in — long enough to read the
// confirming label and re-tap, short enough that a walked-away tab doesn't
// stay armed.
const CLEAR_ARM_TIMEOUT_MS = 5000;

const PRINT_STYLES = `
  @page {
    margin: 14mm;
  }

  @media print {
    :root,
    [data-theme],
    [data-funnel="visa"] {
      --background: #ffffff;
      --foreground: #172033;
      --surface-base: #ffffff;
      --surface-raised: #ffffff;
      --surface-sunken: #f4f6f8;
      --text-primary: #172033;
      --text-secondary: #334155;
      --text-tertiary: #475569;
      --color-text-muted: #475569;
      --color-border-subtle: #cbd5e1;
      --accent-funnel: #8f1d2c;
      --accent-funnel-text: #8f1d2c;
      --bz-elevated: #ffffff;
      --tx-secondary: #334155;
    }

    html,
    body {
      background: #ffffff !important;
      color: #172033 !important;
    }

    nav,
    .fixed.bottom-0.left-0.right-0.z-50,
    .bz-shs-save-plan-bar,
    .bz-shs-option,
    .bz-shs-scenario-toggle-trigger,
    .bz-shs-scenario-toggle-back,
    .bz-shs-back-to-answers {
      display: none !important;
    }

    .mx-auto.max-w-6xl,
    [data-funnel="visa"] {
      max-width: none !important;
      margin: 0 !important;
      padding: 0 !important;
    }

    [data-funnel="visa"] section,
    [data-funnel="visa"] table,
    [data-funnel="visa"] tr,
    [data-funnel="visa"] li {
      break-inside: avoid;
      page-break-inside: avoid;
    }

    [data-funnel="visa"] section {
      box-shadow: none !important;
    }

    [data-funnel="visa"] section > div {
      overflow: visible !important;
    }

    [data-funnel="visa"] table {
      width: 100% !important;
      font-size: 9pt;
    }

    [data-funnel="visa"] th,
    [data-funnel="visa"] td {
      white-space: normal !important;
    }

    [data-funnel="visa"] input[type="checkbox"] {
      appearance: auto;
      print-color-adjust: exact;
      -webkit-print-color-adjust: exact;
    }

    a[href^="https://wa.me"] {
      display: inline !important;
      min-height: 0 !important;
      padding: 0 !important;
      border: 0 !important;
      background: transparent !important;
      color: #172033 !important;
      font-weight: 600;
      text-decoration: none !important;
    }

    a[href^="https://wa.me"] svg {
      display: none !important;
    }

    a[href^="https://wa.me"]::after {
      content: " (" attr(href) ")";
      font-weight: 400;
      overflow-wrap: anywhere;
    }
  }
`;

type RestingClearButtonStyle = {
  borderColor: "var(--text-secondary)";
  color: "var(--text-secondary)";
};

// Compile-time regression guard: the rare destructive action stays neutral
// until the user points to it or focuses it. Changing either value back to an
// error token fails the mouth typecheck instead of silently restoring the red
// clash with the all-inclusive price.
//
// These values are consumed ONLY by CLEAR_BUTTON_STYLES below — never spread
// into the button's own `style` prop. An inline `color`/`border-color` on the
// element itself would permanently out-rank the `:hover`/`:focus-visible`
// class rule below, no matter how that selector is written: an inline style
// attribute beats every stylesheet selector, pseudo-classes included. That
// was the shape of a real bug here — measured live in Chromium, hover left
// color/border-color/background completely unchanged, only the CSS
// properties the inline style didn't also touch (text-decoration, the
// currentColor-driven box-shadow ring's hue aside, outline) moved at all.
const restingClearButtonStyle = {
  borderColor: "var(--text-secondary)",
  color: "var(--text-secondary)",
} satisfies RestingClearButtonStyle;

const CLEAR_BUTTON_STYLES = `
  .bz-shs-clear-plan {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    border: 1px solid ${restingClearButtonStyle.borderColor};
    background: transparent;
    color: ${restingClearButtonStyle.color};
    transition:
      border-color var(--motion-duration-fast, 150ms) ease,
      color var(--motion-duration-fast, 150ms) ease,
      background-color var(--motion-duration-fast, 150ms) ease,
      box-shadow var(--motion-duration-fast, 150ms) ease;
  }

  .bz-shs-clear-plan:is(:hover, :focus-visible) {
    /* The editorial gradient is darkest at the bottom and lightest at the
       top. This mix keeps danger text at >= 4.81:1 even on the lightest
       raised surface plus the active tint, while remaining visibly separate
       from the price red. */
    --bz-shs-clear-active: color-mix(
      in srgb,
      var(--color-error, #c0392b) 40%,
      white
    );
    border-color: var(--bz-shs-clear-active);
    background: color-mix(
      in srgb,
      var(--color-error, #c0392b) 16%,
      transparent
    );
    box-shadow: inset 0 0 0 1px currentColor;
    color: var(--bz-shs-clear-active);
    text-decoration-line: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 0.2em;
  }

  .bz-shs-clear-plan:focus-visible {
    outline: 3px solid var(--bz-shs-clear-active);
    outline-offset: 3px;
  }

  /* Armed state (two-step confirm, P0 2026-08-24): must be visible with NO
     hover/focus needed — a touch tap has no hover, and arming is the moment
     the destructive action becomes real, so the cue can't depend on a
     pointer state the next tap (the confirm) won't have either.
     P0 2026-08-24b/c — two rounds on this one, both grounded on the
     rendered page, not declared CSS:
     Round b tried var(--accent-funnel): on this page's fixed
     [data-theme="editorial"][data-funnel="visa"] scope that's #ff3344 —
     byte-identical to the price panel's border. Fixed by switching to
     --state-warning (amber) — which turned out to just relocate the
     collision: VerdictPanel's edge_case band (property route, or ages
     55-59 — NOT a rare case, the majority of a senior audience hits it)
     paints its OWN border/fill in --state-warning at the same outline +
     light-tint structure. Every hue on this page already carries a
     verdict-band or price-panel meaning (success/info/warning/neutral/
     funnel-red) — hunting for a free one just finds the next collision.
     Round c changes the CHANNEL instead of the hue: a solid, opaque FILL
     block. No verdict band and no price panel ever paints a solid fill —
     they are all a thin border over --surface-raised (or a light
     color-mix tint). The one solid-fill precedent already on this exact
     page is WhatsAppHandoff's CTA (#25D366, WHATSAPP_GREEN) sitting right
     above this button — proof a solid block already reads as "the other
     kind of control" here, distinct from every outlined card regardless
     of which hue it carries. That frees funnel red back up: reused as
     color-mix(in srgb, var(--accent-funnel) 85%, black), the exact
     darkening StudioApp.tsx's primaryNavButtonStyle already derives (see
     its comment above, same file) because flat --accent-funnel under
     white text measures 3.62:1 on this funnel/theme pairing — verified
     4.5:1+ after the 85%-black mix, on both known --accent-funnel
     resolutions. This label is 16px/600 — WCAG "normal text" (no
     large-text exemption) — so 4.5:1 against the fill is the real floor:
     measured 4.82:1 on the rendered page. But the fill itself (a DARK red,
     deliberately mixed toward black so white text clears 4.5:1) only
     measures 2.78:1 against the navy surface behind it — short of the 3:1
     non-text/UI-boundary floor (WCAG 1.4.11). Darkening the fill further
     to help criterion 2 makes criterion 3 worse and vice versa; the two
     floors can't both be met by tuning ONE color. So the boundary is a
     SEPARATE color from the fill: border-color and the inset ring both
     read --text-on-accent (white on this funnel) instead of the fill
     token — white-on-navy clears 3:1 by a wide margin regardless of what
     the interior fill measures, and it's the same color already proven
     for the text. The focus-visible outline below reads the SAME
     --text-on-accent for the identical reason: an outline drawn in the
     dark fill color would inherit its 2.78:1 problem. Do not tidy the
     border/outline back to the fill color, and do not go back to
     --state-warning or a bare/light --accent-funnel outline — all three
     are collisions or contrast failures this fixes. Placed after the
     resting :hover/:focus-visible rule above so equal-specificity source
     order lets it win whether or not the armed button is also hovered. */
  .bz-shs-clear-plan.bz-shs-clear-armed {
    --bz-shs-clear-armed-fill: color-mix(
      in srgb,
      var(--accent-funnel) 85%,
      black
    );
    border-color: var(--text-on-accent, #fff);
    background: var(--bz-shs-clear-armed-fill);
    box-shadow: inset 0 0 0 1px var(--text-on-accent, #fff);
    color: var(--text-on-accent, #fff);
    text-decoration-line: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 0.2em;
  }

  .bz-shs-clear-plan.bz-shs-clear-armed:focus-visible {
    outline: 3px solid var(--text-on-accent, #fff);
    outline-offset: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    .bz-shs-clear-plan {
      transition: none;
    }
  }
`;

export interface SavePlanBarProps {
  plan: PlanState;
  /** Clears localStorage (plan-codec's clearPlan) and resets the wizard to
   *  a fresh plan — owned by StudioApp so the reset also rewinds the step
   *  index. */
  onClear: () => void;
}

const buttonStyle: React.CSSProperties = {
  padding: "var(--space-2, 0.5rem) var(--space-4, 1.1rem)",
  borderRadius: 8,
  border: "1px solid var(--color-border-subtle)",
  background: "transparent",
  color: "var(--text-primary)",
  cursor: "pointer",
  minHeight: 44,
  fontSize: "0.9rem",
  fontFamily: "inherit",
};

// Layout-only for the clear button: deliberately excludes border/background/
// color (those come from buttonStyle for the other three buttons) so
// CLEAR_BUTTON_STYLES above is the sole owner of this button's border,
// background and text color — see the comment on restingClearButtonStyle for
// why that ownership can't be shared with an inline `style` prop.
const clearButtonLayoutStyle: React.CSSProperties = {
  padding: buttonStyle.padding,
  borderRadius: buttonStyle.borderRadius,
  cursor: buttonStyle.cursor,
  minHeight: buttonStyle.minHeight,
  fontSize: buttonStyle.fontSize,
  fontFamily: buttonStyle.fontFamily,
};

/** "Your plan stays on this device" bar (spec §5). Answers auto-save on
 *  every change (StudioApp calls plan-codec's savePlan after each answer)
 *  — the explicit "Save on this device" button here is a reassurance
 *  affordance, not the only save path.
 *
 *  P0-C3(e): this is the ONLY carrier of the shareable plan link — the
 *  WhatsApp handoff no longer transports one. P2-6: the copied link is
 *  built from `relevantPlan(plan)`, not the raw plan, so an
 *  abandoned-branch answer (e.g. a leftover `capital` value after
 *  switching to the property route) never leaks into a shared link. */
export function SavePlanBar({ plan, onClear }: SavePlanBarProps) {
  const [savedFeedback, setSavedFeedback] = useState(false);
  const [copiedFeedback, setCopiedFeedback] = useState(false);

  function handleSave() {
    savePlan(plan);
    setSavedFeedback(true);
    window.setTimeout(() => setSavedFeedback(false), 2500);
  }

  async function handleCopyLink() {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}${STUDIO_PATH}#p=${encodePlanFragment(relevantPlan(plan))}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedFeedback(true);
      window.setTimeout(() => setCopiedFeedback(false), 2500);
    } catch {
      // Clipboard blocked (permissions/private mode) — silent no-op; the
      // user can still select the link text manually if we ever render it.
    }
  }

  function handlePrint() {
    if (typeof window === "undefined" || typeof window.print !== "function") {
      return;
    }
    window.print();
  }

  // Two-step destructive confirm for "Clear saved plan": the first
  // activation only arms the control (label + danger treatment change, no
  // side effect); the second activation actually clears. Works identically
  // for mouse, touch and keyboard because it never depends on :hover — a
  // touch tap has none.
  const [clearArmed, setClearArmed] = useState(false);
  // `setTimeout`/`clearTimeout` (not `window.setTimeout`) to match this
  // codebase's existing ref-typing convention — `"node"` is in tsconfig's
  // `types`, so the bare global resolves to `NodeJS.Timeout`, and
  // `ReturnType<typeof setTimeout>` tracks whichever one is actually
  // returned instead of hardcoding the browser's `number`.
  const clearArmedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  function disarmClear() {
    setClearArmed(false);
    if (clearArmedTimeoutRef.current !== null) {
      clearTimeout(clearArmedTimeoutRef.current);
      clearArmedTimeoutRef.current = null;
    }
  }

  function handleClearActivate() {
    if (clearArmed) {
      disarmClear();
      onClear();
      return;
    }
    setClearArmed(true);
    clearArmedTimeoutRef.current = setTimeout(() => {
      clearArmedTimeoutRef.current = null;
      setClearArmed(false);
    }, CLEAR_ARM_TIMEOUT_MS);
  }

  function handleClearKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "Escape" && clearArmed) {
      disarmClear();
    }
  }

  useEffect(() => {
    return () => {
      if (clearArmedTimeoutRef.current !== null) {
        clearTimeout(clearArmedTimeoutRef.current);
      }
    };
  }, []);

  return (
    <section
      className="bz-shs-save-plan-bar"
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
          fontSize: "clamp(1.1rem, 2.6vw, 1.35rem)",
          color: "var(--text-primary)",
        }}
      >
        {getCopy("savePlanBar.heading")}
      </h2>
      <p style={{ margin: 0, color: "var(--text-primary)", lineHeight: 1.6 }}>
        {getCopy("savePlanBar.body")}
      </p>
      <div
        style={{
          display: "flex",
          gap: "var(--space-2, 0.5rem)",
          flexWrap: "wrap",
        }}
      >
        <button type="button" onClick={handleSave} style={buttonStyle}>
          {getCopy("savePlanBar.saveButton")}
        </button>
        <button type="button" onClick={handleCopyLink} style={buttonStyle}>
          {getCopy("savePlanBar.copyLinkButton")}
        </button>
        <button type="button" onClick={handlePrint} style={buttonStyle}>
          {getCopy("savePlanBar.printButton")}
        </button>
        <button
          type="button"
          onClick={handleClearActivate}
          onBlur={disarmClear}
          onKeyDown={handleClearKeyDown}
          className={
            clearArmed
              ? "bz-shs-clear-plan bz-shs-clear-armed"
              : "bz-shs-clear-plan"
          }
          style={clearButtonLayoutStyle}
        >
          <Trash2 size={16} strokeWidth={1.75} aria-hidden />
          {clearArmed
            ? getCopy("savePlanBar.clearConfirmButton")
            : getCopy("savePlanBar.clearButton")}
        </button>
      </div>
      <div role="status" aria-live="polite" style={{ minHeight: "1.2em" }}>
        {savedFeedback ? (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--text-primary)",
            }}
          >
            {getCopy("savePlanBar.savedConfirmation")}
          </p>
        ) : null}
        {copiedFeedback ? (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--text-primary)",
            }}
          >
            {getCopy("savePlanBar.copiedConfirmation")}
          </p>
        ) : null}
        {clearArmed ? (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--text-primary)",
            }}
          >
            {getCopy("savePlanBar.clearArmedStatus")}
          </p>
        ) : null}
      </div>
      <p
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.8rem)",
          color: "var(--color-text-muted)",
        }}
      >
        {getCopy("savePlanBar.linkWarning")}
      </p>
      <style>{PRINT_STYLES}</style>
      <style>{CLEAR_BUTTON_STYLES}</style>
    </section>
  );
}

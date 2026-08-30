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
    /* MERAH PUTIH DAY (2026-08-31): this block used to re-declare a whole
       token set, because the screen was navy and print had to force a
       light result out of a dark live theme. StudioApp.tsx now applies
       MERAH_PUTIH_DAY_VARS as an INLINE style on the [data-funnel="visa"]
       wrapper this printed content lives inside, and an inline style
       outranks any plain (non-!important) rule, print media included — so
       every re-declaration of a token that set already carries was dead
       weight on the day palette and is gone.
       Three lines survive, for two different reasons:
       --surface-base is pinned by a regression test, though per that same
       precedence fact it is NOT what keeps printed paper white — the
       !important background rule below is.
       --color-text-muted / --color-border-subtle are NOT in
       MERAH_PUTIH_DAY_VARS: they are aliases declared once at :root
       (packages/core/tokens/semantic.css) as var(--text-secondary) /
       var(--border-subtle). A var() inside a custom-property declaration
       is substituted using the cascade AT THE DECLARING ELEMENT, so an
       alias declared at :root can never see a wrapper's inline override —
       it must be re-asserted directly, here. Printed cards read them for
       captions and borders, so both restate the day law's own values. */
    :root,
    [data-theme],
    [data-funnel="visa"] {
      --surface-base: #ffffff;
      --color-text-muted: #475372;
      --color-border-subtle: #e3e1da;
    }

    html,
    body,
    [data-funnel="visa"] {
      /* [data-funnel="visa"] added (2026-08-30): that's the day wrapper
         itself, and StudioApp.tsx gives it its OWN inline
         background: var(--surface-base) — the warm carta #f7f6f2 — which
         paints over whatever html/body alone resolve to. Forcing it here
         too, with !important (the one thing that DOES beat an inline
         style), is what actually keeps the printed page paper-white
         instead of carta-tinted. */
      background: #ffffff !important;
      color: #16213a !important;
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
      color: #16213a !important;
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
    /* MERAH PUTIH DAY (2026-08-30): this used to lighten danger red toward
       white — correct against the retired editorial gradient (darkest at
       the bottom, lightest at the top: a dark ground), where mixing toward
       white was what kept the text from going muddy-dark on a dark bg.
       Screen ground is now a flat, LIGHT carta/white, so lightening further
       is exactly backwards — mixed 40% toward white it measured ~1.5:1
       against its own tint, nowhere near AA. The fix is to stop mixing and
       read --color-error directly: on the day palette that's #a83a44,
       which measures (computed against the literal values above) 4.88:1
       for text against this rule's own 16% background tint (still clears
       4.5:1 at the type's own weight/size) and 6.26:1 for the border/outline
       against the white card exterior (well past the 3:1 boundary floor) —
       and it stays a different hue from the funnel/price red (day
       --color-error #a83a44 vs day --accent-funnel #C8102E /
       --accent-funnel-text #D01033), so the "never collide with the price
       panel" property this rule exists for is untouched. */
    border-color: var(--color-error, #a83a44);
    background: color-mix(
      in srgb,
      var(--color-error, #a83a44) 16%,
      transparent
    );
    box-shadow: inset 0 0 0 1px currentColor;
    color: var(--color-error, #a83a44);
    text-decoration-line: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 0.2em;
  }

  .bz-shs-clear-plan:focus-visible {
    outline: 3px solid var(--color-error, #a83a44);
    outline-offset: 3px;
  }

  /* Armed state (two-step confirm, P0 2026-08-24): must be visible with NO
     hover/focus needed — a touch tap has no hover, and arming is the moment
     the destructive action becomes real, so the cue can't depend on a
     pointer state the next tap (the confirm) won't have either.
     P0 2026-08-24b/c — two rounds on this one, both grounded on the
     rendered page, not declared CSS:
     Two constraints, learned the hard way then and still binding now:
     HUE — every hue on this page already carries a verdict-band or price
     meaning. Bare var(--accent-funnel) was byte-identical to the price
     panel's border, and --state-warning just relocated the collision onto
     VerdictPanel's edge_case band (property route, or ages 55-59 — NOT a
     rare case, the majority of a senior audience hits it). The danger
     family is the one hue this page leaves free: VerdictPanel keeps
     not_eligible deliberately neutral rather than --state-danger.
     CHANNEL — a solid, opaque FILL. No verdict band and no price panel
     ever paints one; they are all a thin border over --surface-raised or a
     light tint. The solid-fill precedent right above this button is
     WhatsAppHandoff's CTA, so a block already reads here as "the other
     kind of control", whatever hue it carries.

     MERAH PUTIH DAY (2026-08-31): the fill was
     color-mix(var(--accent-funnel) 85%, black) ≈ #aa0e27 — a FOURTH red
     belonging to no token. That darkening existed only because flat
     #ff3344 under white measured 3.62:1 on the retired navy scheme; the
     day palette has no such problem, and mixing a brand red toward black
     to make it safe is how a palette grows reds nobody declared. It now
     reads --color-error (#a83a44) neat: white on it measures 6.26:1 (past
     the 4.5:1 floor this 16px/600 label needs — no large-text exemption)
     and it stands 6.26:1 against the white card, clearing the 3:1
     non-text boundary floor (WCAG 1.4.11) unaided. That also makes armed
     the top of ONE scale: this same button already reads --color-error at
     rest and on hover, so the two states no longer speak different reds.
     border/box-shadow/outline stay --text-on-accent (white) — now inert
     reinforcement rather than the thing carrying the 3:1 requirement, and
     pinned by SavePlanBar.test.tsx. Do not restore --state-warning or a
     bare/light --accent-funnel outline: both are collisions this fixes.
     Placed after the resting :hover/:focus-visible rule above so
     equal-specificity source order lets it win whether or not the armed
     button is also hovered. */
  .bz-shs-clear-plan.bz-shs-clear-armed {
    --bz-shs-clear-armed-fill: var(--color-error, #a83a44);
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
  // R4 §3 radius law: 12 for buttons/CTAs (was 8). No nesting exception
  // applies — these buttons sit inside the bar's own 24px section padding
  // (var(--space-4, 1.5rem)), well clear of that section's own 12px
  // corner curve, so there's no tight-nesting mismatch to avoid.
  borderRadius: 12,
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
          // R4 §3 24px floor for Cormorant/serif (low-DPI Android
          // antialiasing shreds it below 1.5rem) — raised from
          // clamp(1.1rem, 2.6vw, 1.35rem) on the day migration.
          fontSize: "clamp(1.5rem, 2.6vw, 1.75rem)",
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

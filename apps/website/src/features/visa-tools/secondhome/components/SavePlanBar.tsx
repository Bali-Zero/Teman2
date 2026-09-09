"use client";

import { useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { getCopy } from "../engine/copy";
import { encodePlanFragment, savePlan } from "../engine/plan-codec";
import { relevantPlan } from "../engine/sequence";
import type { PlanState } from "../engine/types";

const STUDIO_PATH = "/visa/second-home/studio";
const CLEAR_ARM_TIMEOUT_MS = 5000;

const PRINT_STYLES = `
  @page {
    margin: 14mm;
  }

  @media print {

    :root,
    [data-theme],
    [data-funnel="visa"] {
      --surface-base: #ffffff;
      --color-text-muted: #4f5f67;
      --color-border-subtle: #d6cfc2;
    }

    html,
    body,
    [data-funnel="visa"] {

      background: #ffffff !important;
      color: #1D2C3B !important;
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
      color: #1D2C3B !important;
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

  onClear: () => void;
}

const buttonStyle: React.CSSProperties = {
  padding: "var(--space-2, 0.5rem) var(--space-4, 1.1rem)",
  borderRadius: 12,
  border: "1px solid var(--border-strong)",
  background: "transparent",
  color: "var(--text-primary)",
  cursor: "pointer",
  minHeight: 44,
  fontSize: "0.9rem",
  fontFamily: "inherit",
};
const clearButtonLayoutStyle: React.CSSProperties = {
  padding: buttonStyle.padding,
  borderRadius: buttonStyle.borderRadius,
  cursor: buttonStyle.cursor,
  minHeight: buttonStyle.minHeight,
  fontSize: buttonStyle.fontSize,
  fontFamily: buttonStyle.fontFamily,
};

export function SavePlanBar({ plan, onClear }: SavePlanBarProps) {
  const [feedback, setFeedback] = useState<
    | "savedConfirmation"
    | "saveFailed"
    | "copiedConfirmation"
    | "copyFailed"
    | null
  >(null);
  const [showManualLink, setShowManualLink] = useState(false);

  useEffect(() => {
    if (feedback !== "savedConfirmation" && feedback !== "copiedConfirmation")
      return;
    const timeout = window.setTimeout(() => setFeedback(null), 2500);
    return () => window.clearTimeout(timeout);
  }, [feedback]);

  function planLink(): string {
    if (typeof window === "undefined") return "";
    return `${window.location.origin}${STUDIO_PATH}#p=${encodePlanFragment(relevantPlan(plan))}`;
  }

  function handleSave() {
    const saved = savePlan(plan);
    setFeedback(saved ? "savedConfirmation" : "saveFailed");
    setShowManualLink(!saved);
  }

  async function handleCopyLink() {
    if (typeof window === "undefined") return;
    setFeedback(null);
    try {
      await navigator.clipboard.writeText(planLink());
      setFeedback("copiedConfirmation");
      setShowManualLink(false);
    } catch {
      setFeedback("copyFailed");
      setShowManualLink(true);
    }
  }

  function handlePrint() {
    if (typeof window === "undefined" || typeof window.print !== "function") {
      return;
    }
    window.print();
  }
  const [clearArmed, setClearArmed] = useState(false);
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
        {feedback ? (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.85rem)",
              color: "var(--text-primary)",
            }}
          >
            {getCopy(`savePlanBar.${feedback}`)}
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
      {showManualLink ? (
        <label
          style={{
            display: "grid",
            gap: "var(--space-2, 0.5rem)",
            minWidth: 0,
          }}
        >
          {getCopy("savePlanBar.manualLinkLabel")}
          <input
            type="text"
            readOnly
            value={planLink()}
            onFocus={(event) => event.currentTarget.select()}
            style={{
              ...buttonStyle,
              cursor: "text",
              width: "100%",
              minWidth: 0,
              boxSizing: "border-box",
              background: "var(--surface-base)",
            }}
          />
        </label>
      ) : null}
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

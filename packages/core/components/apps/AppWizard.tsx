"use client";

import { useEffect, useRef, useState, type FC, type ReactNode } from "react";
import { useHaptic } from "../../hooks/useHaptic";

export interface WizardStep {
  id: string;
  title: string;
  /** Render props for the step body. */
  render: (helpers: {
    value: unknown;
    setValue: (v: unknown) => void;
    next: () => void;
    back: () => void;
  }) => ReactNode;
  /** Optional custom validation. Return string to block Next, null to allow. */
  validate?: (value: unknown) => string | null;
  /**
   * Compact single-line summary of the answered value. Used by the
   * Stacked Context pattern ("— Italian" above the next step). Keep short.
   * Default: `${step.title}: ${String(value)}`.
   */
  summary?: (value: unknown) => string;
}

export interface AppWizardProps {
  steps: WizardStep[];
  onComplete: (values: Record<string, unknown>) => void;
  /** Optional localStorage key to persist {idx, values} for 1h resume. */
  persistKey?: string;
  onStepChange?: (step: number, total: number) => void;
  onAbandon?: (step: number) => void;
}

const PERSIST_TTL_MS = 60 * 60 * 1000; // 1h

/**
 * Multi-step wizard with Stacked Context (prev step peek above, next
 * step peek below), hairline 2px progress bar, and slide+fade step
 * transitions. Haptic feedback on Next success and final submit.
 *
 * Spec: docs/superpowers/specs/2026-04-20-visa-check-ui-design.md §3
 */
export const AppWizard: FC<AppWizardProps> = ({
  steps,
  onComplete,
  persistKey,
  onStepChange,
  onAbandon,
}) => {
  const [idx, setIdx] = useState(0);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [jiggle, setJiggle] = useState(false);
  const haptic = useHaptic();
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // Restore from localStorage on mount.
  useEffect(() => {
    if (!persistKey || typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(persistKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        ts: number;
        idx: number;
        values: Record<string, unknown>;
      };
      if (Date.now() - parsed.ts <= PERSIST_TTL_MS) {
        setIdx(Math.min(parsed.idx, steps.length - 1));
        setValues(parsed.values ?? {});
      }
    } catch {
      /* ignore corrupt storage */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist.
  useEffect(() => {
    if (!persistKey || typeof window === "undefined") return;
    window.localStorage.setItem(
      persistKey,
      JSON.stringify({ ts: Date.now(), idx, values }),
    );
  }, [idx, values, persistKey]);

  // Telemetry on step change.
  useEffect(() => {
    onStepChange?.(idx, steps.length);
  }, [idx, steps.length, onStepChange]);

  // Abandon handler on unload mid-wizard.
  useEffect(() => {
    const handler = () => {
      if (idx < steps.length) onAbandon?.(idx);
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [idx, steps.length, onAbandon]);

  const step = steps[idx];
  if (!step) return null;

  const setValue = (v: unknown) => {
    setValues((prev) => ({ ...prev, [step.id]: v }));
    setError(null);
  };

  const defaultSummary = (s: WizardStep, v: unknown) =>
    `${s.title}: ${v === undefined || v === null || v === "" ? "?" : String(v)}`;

  const prevStep = idx > 0 ? steps[idx - 1] : null;
  const nextStep = idx + 1 < steps.length ? steps[idx + 1] : null;

  const prevSummary = prevStep
    ? (prevStep.summary?.(values[prevStep.id]) ?? defaultSummary(prevStep, values[prevStep.id]))
    : null;

  const next = () => {
    const currentValue = values[step.id];
    const err = step.validate?.(currentValue) ?? null;
    if (err) {
      setError(err);
      setJiggle(true);
      window.setTimeout(() => setJiggle(false), 320);
      return;
    }
    if (idx === steps.length - 1) {
      if (persistKey && typeof window !== "undefined") {
        window.localStorage.removeItem(persistKey);
      }
      haptic([20, 30, 20]);
      onComplete(values);
      return;
    }
    haptic(6);
    setIdx(idx + 1);
  };

  const back = () => {
    if (idx === 0) return;
    setIdx(idx - 1);
  };

  const progress = ((idx + 1) / steps.length) * 100;

  return (
    <div style={{ display: "grid", gap: "var(--space-4, 1.5rem)", position: "relative" }}>
      {/* Hairline 2px progress bar, top */}
      <div
        role="progressbar"
        aria-valuenow={idx + 1}
        aria-valuemax={steps.length}
        style={{
          position: "absolute",
          top: "-1rem",
          left: 0,
          right: 0,
          height: "2px",
          background: "var(--color-border-subtle)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${progress}%`,
            height: "100%",
            background: "var(--accent-funnel)",
            transition: "width 220ms var(--motion-curve-editorial, ease-out)",
          }}
        />
      </div>

      {/* Step label */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        fontSize: "var(--text-xs, 0.72rem)",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: "var(--color-text-muted)",
      }}>
        <span>Step {idx + 1} of {steps.length}</span>
        <span>{step.title}</span>
      </div>

      {/* Previous step stacked summary */}
      {prevSummary ? (
        <div style={{
          opacity: 0.25,
          fontSize: "var(--text-sm, 0.88rem)",
          fontStyle: "italic",
          paddingBottom: "var(--space-2, 0.5rem)",
          borderBottom: "1px dashed var(--color-border-subtle)",
        }}>
          — {prevSummary}
        </div>
      ) : null}

      {/* Current step body, with jiggle state */}
      <div
        ref={bodyRef}
        style={{
          display: "grid",
          gap: "var(--space-3, 1rem)",
          animation: jiggle
            ? "bz-wizard-jiggle 320ms var(--motion-curve-editorial) both"
            : undefined,
        }}
      >
        {step.render({
          value: values[step.id],
          setValue,
          next,
          back,
        })}
        <style>{`
          @keyframes bz-wizard-jiggle {
            0%, 100% { transform: translateX(0); }
            20%      { transform: translateX(-4px); }
            40%      { transform: translateX(4px); }
            60%      { transform: translateX(-4px); }
            80%      { transform: translateX(4px); }
          }
          @media (prefers-reduced-motion: reduce) {
            [data-wizard-body] { animation: none !important; }
          }
        `}</style>
      </div>

      {/* Next step peek */}
      {nextStep ? (
        <div style={{
          opacity: 0.2,
          fontSize: "var(--text-sm, 0.88rem)",
          fontStyle: "italic",
          paddingTop: "var(--space-2, 0.5rem)",
          borderTop: "1px dashed var(--color-border-subtle)",
        }}>
          — {nextStep.title} ↓
        </div>
      ) : null}

      {/* Error */}
      {error ? (
        <p role="alert" style={{ margin: 0, color: "var(--color-error)", fontSize: "var(--text-sm, 0.88rem)" }}>
          {error}
        </p>
      ) : null}

      {/* Nav buttons */}
      <div style={{ display: "flex", gap: "var(--space-3, 1rem)" }}>
        <button
          type="button"
          onClick={back}
          disabled={idx === 0}
          style={{
            padding: "var(--space-2, 0.5rem) var(--space-4, 1.2rem)",
            borderRadius: "4px",
            border: "1px solid var(--color-border-subtle)",
            background: "transparent",
            cursor: idx === 0 ? "not-allowed" : "pointer",
            color: "var(--text-primary)",
            minHeight: "44px",
          }}
        >
          Back
        </button>
        <button
          type="button"
          onClick={next}
          style={{
            marginLeft: "auto",
            padding: "var(--space-2, 0.5rem) var(--space-4, 1.2rem)",
            borderRadius: "4px",
            border: "none",
            background: "var(--accent-funnel)",
            color: "var(--text-on-accent, #fff)",
            fontWeight: 600,
            cursor: "pointer",
            minHeight: "44px",
          }}
        >
          {idx === steps.length - 1 ? "See result" : "Next"}
        </button>
      </div>
    </div>
  );
};

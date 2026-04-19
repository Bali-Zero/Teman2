"use client";

import { useEffect, useState, type FC, type ReactNode } from "react";

export interface WizardStep {
  id: string;
  title: string;
  /** Render props receive step state helpers. */
  render: (helpers: {
    value: unknown;
    setValue: (v: unknown) => void;
    next: () => void;
    back: () => void;
  }) => ReactNode;
  /** Validation: return error string or null to allow advance. */
  validate?: (value: unknown) => string | null;
}

export interface AppWizardProps {
  steps: WizardStep[];
  onComplete: (values: Record<string, unknown>) => void;
  /** Key used for localStorage state persistence (≤ 1h). */
  persistKey?: string;
  onStepChange?: (step: number, total: number) => void;
  onAbandon?: (step: number) => void;
}

const PERSIST_TTL_MS = 60 * 60 * 1000; // 1h

/** Multi-step form with progress bar, back button, and localStorage
 * resume-within-1h. Used by Visa Match (4 steps), KBLI Builder
 * (3 steps), Tax Gap (2 steps). */
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

  // Restore from localStorage if fresh.
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

  // Fire telemetry on step change + abandon.
  useEffect(() => {
    onStepChange?.(idx, steps.length);
  }, [idx, steps.length, onStepChange]);

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

  const next = () => {
    const currentValue = values[step.id];
    const err = step.validate?.(currentValue) ?? null;
    if (err) {
      setError(err);
      return;
    }
    if (idx === steps.length - 1) {
      if (persistKey && typeof window !== "undefined") {
        window.localStorage.removeItem(persistKey);
      }
      onComplete(values);
      return;
    }
    setIdx(idx + 1);
  };

  const back = () => {
    if (idx === 0) return;
    setIdx(idx - 1);
  };

  const progress = ((idx + 1) / steps.length) * 100;

  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      {/* Progress bar + step label */}
      <div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "var(--text-sm)",
            color: "var(--color-text-muted)",
            marginBottom: "var(--space-1)",
          }}
        >
          <span>
            Step {idx + 1} of {steps.length}
          </span>
          <span>{step.title}</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={idx + 1}
          aria-valuemax={steps.length}
          style={{
            height: 6,
            background: "var(--color-border-subtle)",
            borderRadius: 999,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${progress}%`,
              height: "100%",
              background: "var(--bz-accent, #d4845a)",
              transition: "width 220ms ease",
            }}
          />
        </div>
      </div>

      {/* Current step content */}
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        {step.render({
          value: values[step.id],
          setValue,
          next,
          back,
        })}
      </div>

      {error ? (
        <p
          role="alert"
          style={{
            margin: 0,
            color: "var(--color-error)",
            fontSize: "var(--text-sm)",
          }}
        >
          {error}
        </p>
      ) : null}

      {/* Nav buttons */}
      <div style={{ display: "flex", gap: "var(--space-3)" }}>
        <button
          type="button"
          onClick={back}
          disabled={idx === 0}
          style={{
            padding: "var(--space-2) var(--space-4)",
            borderRadius: 8,
            border: "1px solid var(--color-border-subtle)",
            background: "transparent",
            cursor: idx === 0 ? "not-allowed" : "pointer",
            color: "var(--color-text-primary)",
          }}
        >
          Back
        </button>
        <button
          type="button"
          onClick={next}
          style={{
            marginLeft: "auto",
            padding: "var(--space-2) var(--space-4)",
            borderRadius: 8,
            border: "none",
            background: "var(--bz-accent, #d4845a)",
            color: "#fff",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {idx === steps.length - 1 ? "See result" : "Next"}
        </button>
      </div>
    </div>
  );
};

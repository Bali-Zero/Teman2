"use client";

import { useEffect, useRef, useState } from "react";
import type { WizardStep } from "@balizero/core";

/**
 * The eligibility wizard's own shell — same step contract as core's
 * `AppWizard` (the `WizardStep` type is imported, not copied), drawn in the
 * funnel's R19 skin instead of inline styles.
 *
 * Why not AppWizard, measured on the 2026-09-24 renders rather than argued:
 * its chrome is inline `style` objects, so nothing in `voa-r19.css` can reach
 * it, and three of its pieces worked against an anxious first-time visitor
 * here — a 2px unlabelled hairline for progress, a 20%-opacity italic
 * "— Purpose ↓" peek that read as leftover debug text, and a lone Next button
 * pushed to the far right edge of a 1,070px column. AppWizard also serves
 * the Second Home funnels, so re-skinning it would move surfaces this lane
 * does not own. The behaviour below is AppWizard's, kept on purpose: same
 * one-hour `persistKey` resume, same validate-on-Next (never a disabled
 * button), same `onStepChange` / `onAbandon` / `onComplete` calls.
 *
 * What it adds: every step labelled in the progress rail; answers already
 * given are FILED above the current question (a ledger row with a Change
 * control, not a ghost line); one primary action left on the reading line,
 * full width on a phone, with the reassurance directly under it.
 */

export interface VoaWizardLabels {
  stepOf: (current: number, total: number) => string;
  progress: string;
  back: string;
  next: string;
  finish: string;
  change: string;
  assure: string;
}

export interface VoaWizardProps {
  steps: WizardStep[];
  labels: VoaWizardLabels;
  onComplete: (values: Record<string, unknown>) => void;
  persistKey?: string;
  onStepChange?: (step: number, total: number) => void;
  onAbandon?: (step: number) => void;
}

const PERSIST_TTL_MS = 60 * 60 * 1000;

export function VoaWizard({
  steps,
  labels,
  onComplete,
  persistKey,
  onStepChange,
  onAbandon,
}: VoaWizardProps) {
  const [idx, setIdx] = useState(0);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [nudge, setNudge] = useState(false);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const moved = useRef(false);

  useEffect(() => {
    if (!persistKey) return;
    try {
      const raw = window.localStorage.getItem(persistKey);
      if (!raw) return;
      const saved = JSON.parse(raw) as {
        ts: number;
        idx: number;
        values: Record<string, unknown>;
      };
      if (Date.now() - saved.ts <= PERSIST_TTL_MS) {
        setIdx(Math.min(saved.idx, steps.length - 1));
        setValues(saved.values ?? {});
      }
    } catch {
      /* a corrupt entry is a fresh start, not an error */
    }
    // Resume runs once, on mount — exactly as AppWizard's does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!persistKey) return;
    window.localStorage.setItem(
      persistKey,
      JSON.stringify({ ts: Date.now(), idx, values }),
    );
  }, [idx, values, persistKey]);

  useEffect(() => {
    onStepChange?.(idx, steps.length);
  }, [idx, steps.length, onStepChange]);

  useEffect(() => {
    const handler = () => onAbandon?.(idx);
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [idx, onAbandon]);

  // A step change moves focus to the new question, so a screen reader hears
  // it and a phone scrolls back to it — but never on first paint, where it
  // would steal the page's own starting point.
  useEffect(() => {
    if (!moved.current) return;
    bodyRef.current?.focus({ preventScroll: true });
    bodyRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [idx]);

  const step = steps[idx];
  if (!step) return null;

  const current = values[step.id];
  const ready = (step.validate?.(current) ?? null) === null;
  const last = idx === steps.length - 1;

  const go = (to: number) => {
    moved.current = true;
    setError(null);
    setIdx(to);
  };

  const next = () => {
    const err = step.validate?.(current) ?? null;
    if (err) {
      setError(err);
      setNudge(true);
      window.setTimeout(() => setNudge(false), 320);
      return;
    }
    if (last) {
      if (persistKey) window.localStorage.removeItem(persistKey);
      onComplete(values);
      return;
    }
    go(idx + 1);
  };

  return (
    <div className="voa-wiz">
      <ol className="voa-wiz__rail" aria-label={labels.progress}>
        {steps.map((s, i) => (
          <li
            key={s.id}
            className="voa-wiz__seg"
            data-state={i < idx ? "done" : i === idx ? "current" : "todo"}
            aria-current={i === idx ? "step" : undefined}
          >
            <span className="voa-wiz__seg-n" aria-hidden="true">
              {i + 1}
            </span>
            <span className="voa-wiz__seg-label">{s.title}</span>
          </li>
        ))}
      </ol>

      {/* The rail's numbers carry the position visually; this is its voice. */}
      <p className="voa-wiz__count" aria-live="polite">
        {labels.stepOf(idx + 1, steps.length)}
      </p>

      {idx > 0 ? (
        <div className="voa-wiz__meta">
          <button
            type="button"
            className="voa-wiz__back"
            onClick={() => go(idx - 1)}
          >
            <span aria-hidden="true">←</span> {labels.back}
          </button>
        </div>
      ) : null}

      {idx > 0 ? (
        <dl className="voa-wiz__filed">
          {steps.slice(0, idx).map((s, i) => (
            <div key={s.id} className="voa-wiz__filed-row">
              <dt>{s.title}</dt>
              <dd>{s.summary?.(values[s.id]) ?? String(values[s.id] ?? "")}</dd>
              <button
                type="button"
                className="voa-wiz__change"
                onClick={() => go(i)}
                aria-label={`${labels.change}: ${s.title}`}
              >
                {labels.change}
              </button>
            </div>
          ))}
        </dl>
      ) : null}

      <div
        ref={bodyRef}
        tabIndex={-1}
        className={`voa-wiz__body${nudge ? " voa-wiz__body--nudge" : ""}`}
      >
        {step.render({
          value: current,
          setValue: (v) => {
            setValues((prev) => ({ ...prev, [step.id]: v }));
            setError(null);
          },
          next,
          back: () => (idx > 0 ? go(idx - 1) : undefined),
        })}
      </div>

      {error ? (
        <p role="alert" className="voa-wiz__error">
          {error}
        </p>
      ) : null}

      <div className="voa-wiz__act">
        <button
          type="button"
          className="voa-wiz__next"
          data-ready={ready ? "true" : "false"}
          onClick={next}
        >
          {last ? labels.finish : labels.next}
        </button>
        <p className="voa-wiz__assure">{labels.assure}</p>
      </div>
    </div>
  );
}

"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
export { AppHeroForm } from "./AppHeroForm";
export function AppFrame({
  title,
  subtitle,
  children,
}: {
  funnel?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="visa-tool-frame">
      <header className="visa-tool-hero">
        <p className="visa-tool-eyebrow">Bali Zero · Visa tools</p>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </header>
      <div className="visa-tool-workspace">{children}</div>
      <aside className="visa-tool-note">
        This tool provides preparation guidance. Immigration decides
        applications and the dates on your issued permit govern your stay.{" "}
        <a href="/visa/terms">Tool terms</a> ·{" "}
        <a href="/visa/privacy">Privacy</a>
      </aside>
    </div>
  );
}
export interface WizardStep {
  id: string;
  title: string;
  render: (props: {
    value: unknown;
    setValue: (value: unknown) => void;
    next: () => void;
    back: () => void;
  }) => ReactNode;
  validate?: (value: unknown) => string | null;
  summary?: (value: unknown) => string;
}
/** Recent public answers only. Storage failures never block the interview. */
export function AppWizard({
  steps,
  onComplete,
  persistKey,
  onRestore,
  completeLabel = "See my result",
}: {
  steps: WizardStep[];
  onComplete: (values: Record<string, unknown>) => void | Promise<void>;
  persistKey?: string;
  onRestore?: (values: Record<string, unknown>) => void;
  completeLabel?: string;
}) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [index, setIndex] = useState(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const lock = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (persistKey)
      try {
        const saved = JSON.parse(localStorage.getItem(persistKey) ?? "null");
        if (
          saved &&
          Number.isFinite(saved.ts) &&
          Date.now() >= saved.ts &&
          Date.now() - saved.ts < 3_600_000 &&
          saved.values &&
          typeof saved.values === "object" &&
          !Array.isArray(saved.values)
        ) {
          setValues(saved.values);
          onRestore?.(saved.values);
          setIndex(0);
        }
      } catch {
        /* A blocked or invalid store means a fresh interview. */
      }
    setReady(true);
  }, [persistKey]);
  useEffect(() => {
    if (!ready || !persistKey) return;
    try {
      localStorage.setItem(
        persistKey,
        JSON.stringify({ ts: Date.now(), idx: index, values }),
      );
    } catch {
      /* Continue without storage. */
    }
  }, [values, index, ready, persistKey]);
  const step = steps[index];
  const navigate = (next: number) => {
    setError(null);
    setIndex(next);
    requestAnimationFrame(() => heading.current?.focus());
  };
  const advance = async () => {
    if (lock.current) return;
    const issue = step.validate?.(values[step.id]);
    if (issue) {
      setError(issue);
      return;
    }
    if (index < steps.length - 1) {
      navigate(index + 1);
      return;
    }
    for (let i = 0; i < steps.length; i++) {
      const issue = steps[i].validate?.(values[steps[i].id]);
      if (issue) {
        setIndex(i);
        setError(issue);
        return;
      }
    }
    lock.current = true;
    setPending(true);
    setError(null);
    try {
      await onComplete(values);
    } catch {
      setError(
        "The check could not be completed. Your answers are still here; please try again.",
      );
    } finally {
      lock.current = false;
      setPending(false);
    }
  };
  if (!ready) return <p role="status">Preparing your questions…</p>;
  return (
    <section className="visa-tool-wizard" aria-busy={pending}>
      <p className="visa-tool-eyebrow">
        Question {index + 1} of {steps.length}
      </p>
      <ol className="visa-tool-progress" aria-label="Question progress">
        {steps.map((item, i) => (
          <li key={item.id} aria-current={i === index ? "step" : undefined}>
            <span>{i + 1}</span>
            <span>{item.title}</span>
          </li>
        ))}
      </ol>
      <h2 ref={heading} tabIndex={-1}>
        {step.title}
      </h2>
      <fieldset disabled={pending} className="visa-tool-fields">
        {step.render({
          value: values[step.id],
          setValue: (value) => {
            setError(null);
            setValues((current) => ({ ...current, [step.id]: value }));
          },
          next: () => void advance(),
          back: () => navigate(Math.max(0, index - 1)),
        })}
      </fieldset>
      {error && (
        <p role="alert" className="visa-tool-error">
          {error}
        </p>
      )}
      <div className="visa-tool-actions">
        {index > 0 && (
          <button
            type="button"
            disabled={pending}
            onClick={() => navigate(index - 1)}
          >
            Back
          </button>
        )}
        <button
          type="button"
          className="visa-tool-primary"
          disabled={pending}
          onClick={() => void advance()}
        >
          {pending
            ? "Checking…"
            : index === steps.length - 1
              ? completeLabel
              : "Continue"}
        </button>
      </div>
      <p className="visa-tool-small">
        Saved answers can be resumed in this browser for up to one hour.{" "}
        <button
          type="button"
          className="visa-tool-text-button"
          disabled={pending}
          onClick={() => {
            if (persistKey)
              try {
                localStorage.removeItem(persistKey);
              } catch {}
            setValues({});
            onRestore?.({});
            navigate(0);
          }}
        >
          Start again
        </button>
      </p>
    </section>
  );
}

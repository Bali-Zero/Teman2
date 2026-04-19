"use client";

import type { FC, FormEventHandler, ReactNode } from "react";

export interface AppHeroFormProps {
  /** Short headline rendered above the inputs. */
  headline: string;
  /** 1-3 field slots. Use native <input>/<select> for snappy mobile. */
  children: ReactNode;
  submitLabel: string;
  onSubmit: FormEventHandler<HTMLFormElement>;
  /** Error shown above the submit button. */
  error?: string | null;
  /** Disables submit while a request is in-flight. */
  pending?: boolean;
}

/** Minimal above-the-fold form used by Visa Clock ("which visa + entry
 * date?"), KBLI Decoder ("paste your KBLI code"), etc. */
export const AppHeroForm: FC<AppHeroFormProps> = ({
  headline,
  children,
  submitLabel,
  onSubmit,
  error,
  pending = false,
}) => {
  return (
    <form
      onSubmit={onSubmit}
      style={{
        display: "grid",
        gap: "var(--space-3)",
        padding: "var(--space-4)",
        background: "var(--surface-raised)",
        borderRadius: 12,
      }}
    >
      <p style={{ margin: 0, fontWeight: 600, fontSize: "var(--text-lg)" }}>
        {headline}
      </p>
      {children}
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
      <button
        type="submit"
        disabled={pending}
        className="btn btn-primary"
        style={{
          justifySelf: "start",
          padding: "var(--space-3) var(--space-5)",
          borderRadius: 8,
          border: "none",
          background: "var(--bz-accent, #d4845a)",
          color: "#fff",
          fontWeight: 600,
          cursor: pending ? "wait" : "pointer",
          opacity: pending ? 0.6 : 1,
        }}
      >
        {pending ? "Working…" : submitLabel}
      </button>
    </form>
  );
};

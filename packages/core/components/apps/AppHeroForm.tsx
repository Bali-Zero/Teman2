"use client";

import type { FC, FormEventHandler, ReactNode } from "react";
import { AppSentenceBuilder } from "./AppSentenceBuilder";

export interface AppHeroFormProps {
  headline: string;
  /** Form body — ignored when sentenceTemplate is set. */
  children?: ReactNode;
  submitLabel: string;
  onSubmit: FormEventHandler<HTMLFormElement>;
  /** Shown above the submit button as role=alert. */
  error?: string | null;
  /** Disables submit + shows "Working…" while a request is in-flight. */
  pending?: boolean;
  /**
   * When present, renders AppSentenceBuilder with the supplied fields
   * instead of children. Used by /visa/clock.
   */
  sentenceTemplate?: string;
  sentenceFields?: Record<string, ReactNode>;
}

export const AppHeroForm: FC<AppHeroFormProps> = ({
  headline,
  children,
  submitLabel,
  onSubmit,
  error,
  pending = false,
  sentenceTemplate,
  sentenceFields,
}) => {
  const body = sentenceTemplate ? (
    <AppSentenceBuilder
      template={sentenceTemplate}
      fields={sentenceFields ?? {}}
    />
  ) : (
    children
  );

  return (
    <form
      onSubmit={onSubmit}
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        padding: "var(--space-4, 1.5rem)",
        background: "var(--surface-raised)",
        borderRadius: "12px",
        border: "1px solid var(--color-border-subtle)",
      }}
    >
      <p style={{
        margin: 0,
        fontFamily: "var(--font-serif, Georgia, 'Times New Roman', serif)",
        fontWeight: 400,
        fontSize: "clamp(1.4rem, 3vw, 1.8rem)",
        lineHeight: 1.15,
        color: "var(--text-primary)",
      }}>
        {headline}
      </p>
      {body}
      {error ? (
        <p
          role="alert"
          style={{
            margin: 0,
            color: "var(--color-error)",
            fontSize: "var(--text-sm, 0.88rem)",
          }}
        >
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={pending}
        style={{
          justifySelf: "start",
          padding: "var(--space-3, 0.85rem) var(--space-5, 1.5rem)",
          borderRadius: "4px",
          border: "none",
          background: "var(--accent-funnel)",
          color: "var(--text-on-accent, #fff)",
          fontWeight: 600,
          cursor: pending ? "wait" : "pointer",
          opacity: pending ? 0.6 : 1,
          transition: "opacity var(--motion-duration-accent, 200ms) var(--motion-curve-editorial)",
          minHeight: "44px",
        }}
      >
        {pending ? "Working…" : submitLabel}
      </button>
    </form>
  );
};

"use client";

import type { FC, ReactNode } from "react";

export interface BranchOption {
  id: string;
  title: string;
  description: string;
  icon?: ReactNode;
  href: string;
}

export interface AppBranchSelectorProps {
  question: string;
  options: [BranchOption, BranchOption];
  onSelect?: (option: BranchOption) => void;
}

/** 2-card branch picker used by the visa entry page ("Are you in Indonesia?")
 * and by kbli entry ("Do you already have a PT PMA?"). Click emits onSelect
 * and navigates via the `href` (Next.js <a> — progressive enhancement). */
export const AppBranchSelector: FC<AppBranchSelectorProps> = ({
  question,
  options,
  onSelect,
}) => {
  return (
    <div
      role="group"
      aria-label={question}
      style={{ display: "grid", gap: "var(--space-4)" }}
    >
      <p style={{ fontSize: "var(--text-xl)", margin: 0, fontWeight: 600 }}>
        {question}
      </p>
      <div
        style={{
          display: "grid",
          gap: "var(--space-3)",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        }}
      >
        {options.map((opt) => (
          <a
            key={opt.id}
            href={opt.href}
            onClick={() => onSelect?.(opt)}
            style={{
              display: "grid",
              gap: "var(--space-2)",
              padding: "var(--space-4)",
              borderRadius: 12,
              border: "1px solid var(--color-border-subtle)",
              background: "var(--surface-raised)",
              textDecoration: "none",
              color: "var(--color-text-primary)",
              minHeight: 120,
            }}
          >
            {opt.icon ? <div aria-hidden>{opt.icon}</div> : null}
            <strong style={{ fontSize: "var(--text-lg)" }}>{opt.title}</strong>
            <span
              style={{
                color: "var(--color-text-muted)",
                fontSize: "var(--text-sm)",
                lineHeight: 1.4,
              }}
            >
              {opt.description}
            </span>
          </a>
        ))}
      </div>
    </div>
  );
};

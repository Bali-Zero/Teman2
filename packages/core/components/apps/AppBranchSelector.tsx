"use client";

import type { FC, ReactNode } from "react";
import { useHaptic } from "../../hooks/useHaptic";

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

/**
 * 2-card branch picker used by /visa (Clock vs Match) and /kbli
 * (Decoder vs Builder). Click fires onSelect, navigates via href,
 * and emits a small haptic (iOS16.4+). See spec §1 Hero entry page.
 */
export const AppBranchSelector: FC<AppBranchSelectorProps> = ({
  question,
  options,
  onSelect,
}) => {
  const haptic = useHaptic();
  const handleClick = (opt: BranchOption) => {
    haptic(8);
    onSelect?.(opt);
  };
  return (
    <div
      role="group"
      aria-label={question}
      style={{ display: "grid", gap: "var(--space-3, 1rem)" }}
    >
      <p style={{
        fontSize: "clamp(1.1rem, 2.4vw, 1.25rem)",
        margin: 0,
        fontWeight: 600,
        color: "var(--text-primary)",
      }}>
        {question}
      </p>
      <div style={{
        display: "grid",
        gap: "var(--space-2, 0.5rem)",
      }}>
        {options.map((opt) => (
          <a
            key={opt.id}
            href={opt.href}
            onClick={() => handleClick(opt)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              minHeight: "56px",
              padding: "var(--space-3, 0.9rem) var(--space-4, 1.2rem)",
              borderRadius: "4px",
              border: "1px solid var(--color-border-subtle)",
              background: "var(--surface-raised)",
              textDecoration: "none",
              color: "var(--text-primary)",
              transition: "border-color var(--motion-duration-base, 250ms) var(--motion-curve-editorial), background-color var(--motion-duration-base, 250ms) var(--motion-curve-editorial)",
            }}
          >
            <span style={{ display: "grid", gap: "var(--space-1, 0.25rem)" }}>
              <strong style={{ fontWeight: 600, fontSize: "var(--text-md, 1rem)" }}>
                {opt.title}
              </strong>
              <span style={{
                color: "var(--color-text-muted)",
                fontSize: "var(--text-sm, 0.88rem)",
                lineHeight: 1.4,
              }}>
                {opt.description}
              </span>
            </span>
            <span aria-hidden style={{
              color: "var(--color-text-muted)",
              fontSize: "1.25rem",
            }}>
              →
            </span>
          </a>
        ))}
      </div>
    </div>
  );
};

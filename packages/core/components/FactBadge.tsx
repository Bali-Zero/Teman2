import type { CSSProperties, FC, ReactNode } from "react";

export interface FactBadgeProps {
  children: ReactNode;
  className?: string;
  title?: string;
}

const STYLE: CSSProperties = {
  background: "var(--fact-badge-bg)",
  color: "var(--fact-badge-fg)",
  fontFamily: "var(--font-mono, monospace)",
  borderRadius: "var(--fact-badge-radius)",
  padding: "2px 6px",
  fontSize: "0.75em",
};

/**
 * FactBadge — "yellow = verifiable facts" marker (bali-zero-brand
 * regulation_badge). Used for KBLI codes, citations, regulation codes.
 * Funnel-agnostic: reads only --fact-badge-* semantic tokens, never
 * --accent-funnel, so it is safe inside and outside data-funnel scopes.
 */
export const FactBadge: FC<FactBadgeProps> = ({
  children,
  className,
  title,
}) => {
  return (
    <span
      data-role="fact-badge"
      className={className ? `fact-badge ${className}` : "fact-badge"}
      title={title}
      style={STYLE}
    >
      {children}
    </span>
  );
};

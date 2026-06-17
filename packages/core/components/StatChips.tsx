import React from "react";

export interface StatChip {
  key: string;
  content: React.ReactNode;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  title?: string;
  ariaLabel?: string;
}

export interface StatChipsProps {
  items: Array<StatChip | false | null | undefined>;
  className?: string;
  chipClassName?: string;
}

/**
 * Row of stat / quick-filter pills shared by workspace list pages. Chips with
 * an `onClick` render as buttons, the rest as static spans. Falsy items are
 * skipped (allows inline `cond && {…}`); per-chip `className` is appended to
 * the shared `chipClassName` base.
 */
export function StatChips({
  items,
  className = "flex flex-wrap gap-2 text-xs",
  chipClassName = "flex items-center gap-1 px-2.5 py-1 rounded-full",
}: StatChipsProps) {
  return (
    <div className={className}>
      {items
        .filter((item): item is StatChip => Boolean(item))
        .map((item) => {
          const cls = item.className
            ? `${chipClassName} ${item.className}`
            : chipClassName;
          return item.onClick ? (
            <button
              key={item.key}
              type="button"
              onClick={item.onClick}
              className={cls}
              style={item.style}
              title={item.title}
              aria-label={item.ariaLabel}
            >
              {item.content}
            </button>
          ) : (
            <span
              key={item.key}
              className={cls}
              style={item.style}
              title={item.title}
              aria-label={item.ariaLabel}
            >
              {item.content}
            </span>
          );
        })}
    </div>
  );
}

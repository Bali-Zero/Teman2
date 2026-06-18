import React from "react";

export interface ListPageHeaderProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}

/**
 * Shared header row for workspace list pages: bold title + muted subtitle on
 * the left, action controls on the right.
 */
export function ListPageHeader({
  title,
  subtitle,
  actions,
}: ListPageHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          {title}
        </h1>
        {subtitle != null && (
          <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
            {subtitle}
          </p>
        )}
      </div>
      {actions != null && (
        <div className="flex items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

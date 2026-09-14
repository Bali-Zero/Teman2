import React from "react";
import { DESK_RULE, DESK_SERIF } from "./deskStrip";

export interface ListPageHeaderProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  /**
   * `"desk"` is the R19 masthead: a copper rule, the title in Fraunces, the
   * actions still on the right. Opt-in, so every page that has not been
   * rebuilt keeps the header it was designed with — the default branch below
   * is byte-identical to what shipped.
   */
  variant?: "default" | "desk";
}

/**
 * Shared header row for workspace list pages: bold title + muted subtitle on
 * the left, action controls on the right.
 */
export function ListPageHeader({
  title,
  subtitle,
  actions,
  variant = "default",
}: ListPageHeaderProps) {
  if (variant === "desk") {
    return (
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div aria-hidden="true" className={DESK_RULE} />
          <h1
            className="text-[32px] leading-[1.05] tracking-[-0.035em]"
            style={{ ...DESK_SERIF, color: "var(--tx-pure)" }}
          >
            {title}
          </h1>
          {subtitle != null && (
            <p
              className="mt-[7px] text-[12px]"
              style={{ color: "var(--tx-secondary)" }}
            >
              {subtitle}
            </p>
          )}
        </div>
        {actions != null && (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        )}
      </div>
    );
  }

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

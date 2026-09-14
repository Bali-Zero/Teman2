import React from "react";
import { DESK_FIELD, DESK_SERIF } from "./deskStrip";

export interface FilterBarProps {
  activeCount: number;
  onClearAll: () => void;
  className?: string;
  style?: React.CSSProperties;
  gridClassName?: string;
  clearLabel?: React.ReactNode;
  children: React.ReactNode;
  /**
   * `"desk"` frames the panel with the strip's hairlines instead of a card,
   * sets the heading in Fraunces and makes Clear-all a copper text link.
   * Opt-in — the default branch is byte-identical to what shipped.
   */
  variant?: "default" | "desk";
}

/**
 * Expanded filters panel shared by workspace list pages: "Filters" heading,
 * Clear-all action (shown when `activeCount > 0`) and a grid of filter
 * fields. `className` is appended to the `p-4 space-y-4` panel base.
 */
export function FilterBar({
  activeCount,
  onClearAll,
  className,
  style,
  gridClassName = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4",
  clearLabel = "Clear all",
  children,
  variant = "default",
}: FilterBarProps) {
  if (variant === "desk") {
    return (
      <div
        className={
          className
            ? `border-b border-[var(--bz-border)] py-4 space-y-4 ${className}`
            : "border-b border-[var(--bz-border)] py-4 space-y-4"
        }
        style={style}
      >
        <div className="flex items-center justify-between">
          <h3
            className="text-[18px] leading-none"
            style={{ ...DESK_SERIF, color: "var(--tx-pure)" }}
          >
            Filters
          </h3>
          {activeCount > 0 && (
            <button
              type="button"
              onClick={onClearAll}
              className="flex min-h-11 items-center gap-1 text-[12px] font-[700] text-[var(--bz-copper-text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
            >
              {clearLabel}
            </button>
          )}
        </div>
        <div className={gridClassName}>{children}</div>
      </div>
    );
  }

  return (
    <div
      className={className ? `p-4 space-y-4 ${className}` : "p-4 space-y-4"}
      style={style}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-medium" style={{ color: "var(--bz-text-1)" }}>
          Filters
        </h3>
        {activeCount > 0 && (
          <button
            type="button"
            onClick={onClearAll}
            className="text-sm hover:underline flex items-center gap-1"
            style={{ color: "var(--bz-accent)" }}
          >
            {clearLabel}
          </button>
        )}
      </div>
      <div className={gridClassName}>{children}</div>
    </div>
  );
}

export interface FilterSelectProps {
  label: React.ReactNode;
  labelExtra?: React.ReactNode;
  value: string;
  onChange: (value: string) => void;
  id?: string;
  selectClassName?: string;
  selectStyle?: React.CSSProperties;
  children: React.ReactNode;
  /** `"desk"` puts the select on the 44px control boundary, square. */
  variant?: "default" | "desk";
}

const SELECT_BASE = "w-full px-3 py-2 rounded-lg focus:outline-none";

/** Labelled `<select>` field for the FilterBar grid. */
export function FilterSelect({
  label,
  labelExtra,
  value,
  onChange,
  id,
  selectClassName,
  selectStyle,
  children,
  variant = "default",
}: FilterSelectProps) {
  const desk = variant === "desk";
  const labelEl = (
    <label
      htmlFor={id}
      className={
        desk
          ? `block text-[10px] font-[700] uppercase tracking-[0.12em] text-[var(--tx-secondary)]${labelExtra ? "" : " mb-1.5"}`
          : labelExtra
            ? "block text-sm font-medium"
            : "block text-sm font-medium mb-1.5"
      }
      style={desk ? undefined : { color: "var(--bz-text-2)" }}
    >
      {label}
    </label>
  );
  return (
    <div>
      {labelExtra ? (
        <div className="flex items-center justify-between mb-1.5">
          {labelEl}
          {labelExtra}
        </div>
      ) : (
        labelEl
      )}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={(() => {
          const base = desk ? DESK_FIELD : SELECT_BASE;
          return selectClassName ? `${base} ${selectClassName}` : base;
        })()}
        style={desk ? undefined : selectStyle}
      >
        {children}
      </select>
    </div>
  );
}

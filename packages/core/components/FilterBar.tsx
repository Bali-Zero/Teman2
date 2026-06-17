import React from "react";

export interface FilterBarProps {
  activeCount: number;
  onClearAll: () => void;
  className?: string;
  style?: React.CSSProperties;
  gridClassName?: string;
  clearLabel?: React.ReactNode;
  children: React.ReactNode;
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
}: FilterBarProps) {
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
}: FilterSelectProps) {
  const labelEl = (
    <label
      htmlFor={id}
      className={
        labelExtra
          ? "block text-sm font-medium"
          : "block text-sm font-medium mb-1.5"
      }
      style={{ color: "var(--bz-text-2)" }}
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
        className={
          selectClassName ? `${SELECT_BASE} ${selectClassName}` : SELECT_BASE
        }
        style={selectStyle}
      >
        {children}
      </select>
    </div>
  );
}

import React from "react";
import { formatIDR, formatIDRCompact } from "../utils/currency";

export interface MoneyProps {
  /** Amount in rupiah. */
  value: number;
  /** Compact "Rp 1.85M" instead of full "Rp 1.850.000". */
  compact?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * The one way to render an IDR amount. Wraps the canonical formatters and
 * keeps digits tabular so money columns align.
 */
export function Money({
  value,
  compact = false,
  className,
  style,
}: MoneyProps) {
  return (
    <span
      className={className}
      style={{ fontVariantNumeric: "tabular-nums", ...style }}
    >
      {compact ? formatIDRCompact(value) : formatIDR(value)}
    </span>
  );
}

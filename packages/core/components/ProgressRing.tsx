import type { FC } from "react";

export interface ProgressRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  status?: "ok" | "warn" | "danger" | "neutral";
  label?: string;
}

/* WS3 (GARUDA Day Edition): the old --color-status-ok/warn/danger and
   --accent-copper names were never declared in the token SSOT — the ring
   strokes resolved to `unset` and disappeared. Read the semantic --state-*
   tokens (WS2 operative-light AA overrides) + --accent-warm (copper). */
const STATUS_TOKEN: Record<NonNullable<ProgressRingProps["status"]>, string> = {
  ok: "var(--state-success)",
  warn: "var(--state-warning)",
  danger: "var(--state-danger)",
  neutral: "var(--accent-warm)",
};

export const ProgressRing: FC<ProgressRingProps> = ({
  percent,
  size = 48,
  strokeWidth = 4,
  status = "neutral",
  label,
}) => {
  const clamped = Math.max(0, Math.min(100, percent));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div
      role="img"
      aria-label={`${clamped}% complete`}
      style={{
        width: size,
        height: size,
        display: "inline-block",
        position: "relative",
      }}
    >
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="var(--color-border-subtle)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          data-role="fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={STATUS_TOKEN[status]}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span
        data-role="label"
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: size / 4,
          fontVariantNumeric: "tabular-nums",
          color: "var(--color-text-primary, var(--text-primary))",
        }}
      >
        {label ?? `${clamped}%`}
      </span>
    </div>
  );
};

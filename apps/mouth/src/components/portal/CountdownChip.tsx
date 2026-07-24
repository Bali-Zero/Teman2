import React from "react";

/**
 * CountdownChip — shared portal deadline / age pill.
 *
 * WS3 (GARUDA Day Edition, 2026-07-24): dark-only Tailwind utilities
 * (text-red-400, bg-amber-500/10, …) replaced by the semantic --state-*
 * tokens with color-mix tints, so the chip holds AA on the operative-light
 * paper (WS2 overrides) and reproduces the same hues on dark (state
 * primitives are the same hexes). Age chip reads --glass-rim (armed in both
 * themes) instead of rgba(255,255,255,0.04), which was invisible on paper.
 */

interface CountdownChipProps {
  /** ISO date string to count down to (future) or since (past) */
  date: string;
  /** 'countdown' = future deadline, 'age' = time since event */
  mode?: "countdown" | "age";
  className?: string;
}

function toneStyle(token: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, var(${token}) 12%, transparent)`,
    color: `var(${token})`,
  };
}

export function CountdownChip({
  date,
  mode = "countdown",
  className,
}: CountdownChipProps) {
  const now = Date.now();
  const target = new Date(date).getTime();
  const diffDays = Math.round((target - now) / 86400000);

  if (mode === "age") {
    const ageDays = Math.abs(diffDays);
    if (ageDays < 7) return null;
    const label =
      ageDays >= 365
        ? `${Math.floor(ageDays / 365)}y ago`
        : ageDays >= 30
          ? `${Math.floor(ageDays / 30)}mo ago`
          : `${ageDays}d ago`;
    return (
      <span
        suppressHydrationWarning
        className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${className ?? ""}`}
        style={{
          background: "var(--glass-rim)",
          /* --bz-text-2: --bz-text-3 computes 3.06:1 on this tint over white
             cards — below the 4.5:1 small-text floor (WS3 AA pass). */
          color: "var(--bz-text-2)",
        }}
      >
        {label}
      </span>
    );
  }

  // Countdown mode
  const isOverdue = diffDays < 0;
  const absDays = Math.abs(diffDays);

  const chipStyle = isOverdue
    ? toneStyle("--state-danger")
    : diffDays <= 7
      ? toneStyle("--state-danger")
      : diffDays <= 90
        ? toneStyle("--state-warning")
        : toneStyle("--state-success");

  const label = isOverdue
    ? `${absDays}d overdue`
    : diffDays === 0
      ? "today"
      : diffDays === 1
        ? "tomorrow"
        : diffDays <= 365
          ? `⏰ ${diffDays}d left`
          : `${Math.floor(diffDays / 30)}mo left`;

  return (
    <span
      suppressHydrationWarning
      className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${className ?? ""}`}
      style={chipStyle}
      title={new Date(date).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      })}
    >
      {label}
    </span>
  );
}

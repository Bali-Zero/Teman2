"use client";

import { glassCard, getRoleColor, getInitials } from "./editorial-tokens";

interface Associate {
  client_name?: string;
  role: string;
  ownership_percentage?: number;
  shares_count?: number;
}

interface PeopleColumnProps {
  associates: Associate[];
  fallbackName?: string;
}

export function PeopleColumn({ associates, fallbackName }: PeopleColumnProps) {
  if (associates.length === 0) return null;

  // Build equity bar segments
  const equitySegments = associates
    .filter((a) => a.ownership_percentage && a.ownership_percentage > 0)
    .map((a) => {
      const colors = getRoleColor(a.role);
      return { pct: a.ownership_percentage!, color: colors.accent };
    });

  const totalPct = equitySegments.reduce((sum, s) => sum + s.pct, 0);
  const equityLabel =
    equitySegments.length === 2 &&
    equitySegments[0].pct === equitySegments[1].pct
      ? `Equal ${equitySegments[0].pct} / ${equitySegments[1].pct} split`
      : `${equitySegments.length} shareholders`;

  return (
    <div className="flex flex-col gap-4">
      {/* Section intro */}
      <div className="text-[12px] text-[var(--kbli-text-muted)] uppercase tracking-[0.1em] font-semibold pb-4 border-b border-[var(--kbli-border)]">
        Shareholders & Officers
      </div>

      {/* Person cards */}
      {associates.map((a, i) => {
        const name = a.client_name || fallbackName || "?";
        const initials = getInitials(name);
        const colors = getRoleColor(a.role);

        return (
          <div
            key={i}
            className="relative overflow-hidden rounded-[var(--kbli-radius-lg)] p-[22px] flex flex-col gap-3.5 transition-all hover:translate-y-[-1px]"
            style={glassCard}
          >
            {/* Top accent line */}
            <div
              className="absolute top-0 left-[22px] h-0.5 w-8 rounded-b-sm"
              style={{ background: colors.accent }}
            />

            {/* Header: initials + name + percentage */}
            <div className="flex items-start justify-between gap-3">
              <div
                className="w-[42px] h-[42px] rounded-[var(--kbli-radius-md)] flex items-center justify-center text-[13px] font-[800] shrink-0"
                style={{
                  background: colors.bg,
                  border: `1px solid ${colors.border}`,
                  color: colors.accent,
                }}
              >
                {initials}
              </div>
              <div className="flex-1">
                <div className="text-[15px] font-bold text-[var(--kbli-text-primary)] leading-[1.2]">
                  {name}
                </div>
                <div className="text-[12px] text-[var(--kbli-text-secondary)] mt-0.5 capitalize">
                  {a.role || "Shareholder"}
                </div>
              </div>
              {a.ownership_percentage != null && (
                <span
                  className="text-[22px] font-[800] tabular-nums tracking-[-0.03em] leading-none"
                  style={{ color: colors.accent }}
                >
                  {a.ownership_percentage}%
                </span>
              )}
            </div>

            {/* Detail grid */}
            <div className="grid grid-cols-2 gap-2.5">
              {a.shares_count != null && (
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-[var(--kbli-text-muted)]">
                    Shares
                  </span>
                  <span className="text-[12px] text-[var(--kbli-text-primary)] font-medium tabular-nums">
                    {a.shares_count.toLocaleString()}
                  </span>
                </div>
              )}
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-[var(--kbli-text-muted)]">
                  Role
                </span>
                <span className="text-[12px] text-[var(--kbli-text-primary)] font-medium capitalize">
                  {a.role || "Shareholder"}
                </span>
              </div>
            </div>
          </div>
        );
      })}

      {/* Equity bar */}
      {equitySegments.length >= 2 && (
        <div
          className="p-3 px-4 rounded-[var(--kbli-radius-md)] flex items-center gap-2.5"
          style={glassCard}
        >
          <div
            className="flex-1 h-1 rounded-full overflow-hidden flex"
          >
            {equitySegments.map((seg, i) => (
              <div
                key={i}
                style={{
                  width: `${(seg.pct / totalPct) * 100}%`,
                  background: seg.color,
                }}
                className="h-full"
              />
            ))}
          </div>
          <span className="text-[11px] text-[var(--kbli-text-muted)] whitespace-nowrap">
            {equityLabel}
          </span>
        </div>
      )}
    </div>
  );
}

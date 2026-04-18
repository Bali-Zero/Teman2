import * as React from "react";

interface TrustStat {
  value: string;
  label: string;
  hint?: string;
}

interface TrustBadgesProps {
  stats?: TrustStat[];
  variant?: "row" | "grid";
  className?: string;
}

const DEFAULT_STATS: TrustStat[] = [
  { value: "5,000+", label: "Clients served", hint: "since 2020" },
  { value: "68,000+", label: "Legal documents", hint: "indexed" },
  { value: "4.9/5", label: "Average rating", hint: "Google Reviews" },
  { value: "15 min", label: "Response time", hint: "business hours" },
];

export function TrustBadges({
  stats = DEFAULT_STATS,
  variant = "grid",
  className = "",
}: Readonly<TrustBadgesProps>) {
  const layout =
    variant === "row"
      ? "flex flex-wrap items-center justify-center gap-x-8 gap-y-4"
      : "grid grid-cols-2 sm:grid-cols-4 gap-4";

  return (
    <ul aria-label="Bali Zero trust signals" className={`${layout} ${className}`}>
      {stats.map((stat) => (
        <li
          key={stat.label}
          className="flex flex-col items-center text-center gap-1 p-4 rounded-xl"
          style={{
            backgroundColor: "var(--bz-elevated, rgba(255,255,255,0.04))",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <span
            className="text-2xl sm:text-3xl font-bold"
            style={{ color: "var(--bz-accent, #d4845a)" }}
          >
            {stat.value}
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider">
            {stat.label}
          </span>
          {stat.hint ? (
            <span
              className="text-[11px]"
              style={{ color: "var(--tx-secondary, rgba(255,255,255,0.55))" }}
            >
              {stat.hint}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

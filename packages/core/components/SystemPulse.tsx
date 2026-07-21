import type { CSSProperties, FC } from "react";

export interface SystemPulseService {
  id: string;
  /** Service name rendered as the row title (e.g. "PostgreSQL · Fly.io"). */
  label: string;
  /** Muted mono subtitle under the title (e.g. "prod · ap-southeast"). */
  detail?: string;
  status: "ok" | "warn" | "down" | "idle";
  /** When provided, rendered as "<n>ms"; otherwise the status word is shown. */
  latencyMs?: number;
  /** Latency bar fill 0–100 (clamped). Bar renders only when provided. */
  barPct?: number;
}

export interface SystemPulseProps {
  services: SystemPulseService[];
  className?: string;
}

/**
 * Status → semantic state token. `idle` deliberately reads the muted text
 * token instead of a state color (a sleeping service is not "successful").
 */
const STATUS_COLOR: Record<SystemPulseService["status"], string> = {
  ok: "var(--state-success)",
  warn: "var(--state-warning)",
  down: "var(--state-danger)",
  idle: "var(--text-tertiary)",
};

/**
 * Derives the 2–3 letter mono badge from the service label (mockup's `.ic`
 * cell): first letter of the first two alphanumeric words, or the first two
 * letters of a single-word label. Deterministic — prop-derived, never stored.
 */
export function serviceBadge(label: string): string {
  const words = label.split(/[^a-zA-Z0-9]+/).filter(Boolean);
  if (words.length === 0) return "??";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

const ROOT_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "6px 18px 16px",
};

const BADGE_STYLE: CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: 8,
  background: "var(--surface-sunken)",
  border: "1px solid var(--border-default)",
  display: "grid",
  placeItems: "center",
  fontSize: 9,
  color: "var(--text-secondary)",
  flex: "none",
};

const TITLE_STYLE: CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "var(--text-primary)",
};

const DETAIL_STYLE: CSSProperties = {
  display: "block",
  fontSize: 9.5,
  color: "var(--text-secondary)",
};

const LAT_STYLE: CSSProperties = {
  marginLeft: "auto",
  textAlign: "right",
};

const LAT_VALUE_STYLE: CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
};

const BAR_TRACK_STYLE: CSSProperties = {
  display: "block",
  width: 64,
  height: 3,
  borderRadius: 2,
  background: "var(--border-default)",
  marginTop: 4,
  marginLeft: "auto",
  overflow: "hidden",
};

const BAR_FILL_BASE_STYLE: CSSProperties = {
  display: "block",
  height: "100%",
  borderRadius: 2,
};

/**
 * SystemPulse — live-stack service rows for the kita workspace (GARUDA OS
 * concept "System Pulse" panel). Funnel-agnostic: reads only semantic state /
 * surface / text / border tokens, never --accent-funnel, so it is safe inside
 * and outside data-funnel scopes. All content is prop-driven.
 */
export const SystemPulse: FC<SystemPulseProps> = ({ services, className }) => {
  return (
    <div
      role="list"
      data-role="system-pulse"
      className={className ? `system-pulse ${className}` : "system-pulse"}
      style={ROOT_STYLE}
    >
      {services.map((svc, i) => {
        const color = STATUS_COLOR[svc.status];
        const pct =
          svc.barPct === undefined
            ? undefined
            : Math.max(0, Math.min(100, svc.barPct));
        return (
          <div
            key={svc.id}
            role="listitem"
            data-role="service-row"
            data-status={svc.status}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "10px 0",
              borderBottom:
                i < services.length - 1
                  ? "1px solid var(--border-default)"
                  : "none",
            }}
          >
            <span
              data-role="service-badge"
              className="font-mono"
              style={BADGE_STYLE}
            >
              {serviceBadge(svc.label)}
            </span>
            <span>
              <span data-role="service-title" style={TITLE_STYLE}>
                {svc.label}
              </span>
              {svc.detail !== undefined && (
                <span
                  data-role="service-detail"
                  className="font-mono"
                  style={DETAIL_STYLE}
                >
                  {svc.detail}
                </span>
              )}
            </span>
            <span data-role="service-latency" style={LAT_STYLE}>
              <span className="sr-only">
                Status: {svc.status.toUpperCase()}
              </span>
              <span
                data-role="service-latency-value"
                className="font-mono"
                style={{ ...LAT_VALUE_STYLE, color }}
              >
                {svc.latencyMs !== undefined
                  ? `${svc.latencyMs}ms`
                  : svc.status.toUpperCase()}
              </span>
              {pct !== undefined && (
                <span data-role="service-bar" style={BAR_TRACK_STYLE}>
                  <span
                    data-role="service-bar-fill"
                    style={{
                      ...BAR_FILL_BASE_STYLE,
                      width: `${pct}%`,
                      background: color,
                    }}
                  />
                </span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
};

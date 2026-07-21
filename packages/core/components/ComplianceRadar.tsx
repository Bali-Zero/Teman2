import type { CSSProperties, FC } from "react";

export interface ComplianceAlert {
  id: string;
  /** Alert title (e.g. "KITAS expiry < 30 days"). */
  title: string;
  /** Muted mono subtitle (e.g. "CLI-2207 · renewal pack ready"). */
  detail?: string;
  severity: "critical" | "urgent" | "warning" | "info";
  /** Right-aligned mono time-left string (e.g. "6d"); strong when critical. */
  timeLeft?: string;
}

export interface ComplianceRadarProps {
  alerts: ComplianceAlert[];
  className?: string;
}

/**
 * Severity → semantic token for the dot. Token notes:
 * - `critical` reads --status-critical as a non-text FILL (the token's
 *   documented fill usage); the matching time-left TEXT reads --state-danger
 *   instead, because --status-critical's own contract forbids text on dark
 *   surfaces (~2.54:1) and names --state-danger as the dark-surface text tone.
 * - `warning` reuses --fact-badge-bg (gold #f4c430): the mockup's warning
 *   tone is the KBLI funnel gold (#eab308), which funnels may not read here
 *   (funnel-agnostic panel); --fact-badge-bg is the closest existing
 *   semantic gold and keeps `urgent` (--state-warning, amber) distinct.
 */
const SEVERITY_DOT: Record<ComplianceAlert["severity"], string> = {
  critical: "var(--status-critical)",
  urgent: "var(--state-warning)",
  warning: "var(--fact-badge-bg)",
  info: "var(--state-info)",
};

const ROOT_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "6px 18px 14px",
};

const DOT_BASE_STYLE: CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: "50%",
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

const WHEN_STYLE: CSSProperties = {
  marginLeft: "auto",
  textAlign: "right",
};

const TIME_BASE_STYLE: CSSProperties = {
  fontSize: 10,
  color: "var(--text-secondary)",
};

const TIME_CRITICAL_STYLE: CSSProperties = {
  fontSize: 12,
  fontWeight: 700,
  color: "var(--state-danger)",
};

/**
 * ComplianceRadar — severity-ranked alert rows for the kita workspace
 * (GARUDA OS concept "Compliance Radar" panel). Funnel-agnostic: reads only
 * semantic state / fact-badge / text / border tokens, never --accent-funnel,
 * so it is safe inside and outside data-funnel scopes. All content is
 * prop-driven; rows render from `alerts` only.
 */
export const ComplianceRadar: FC<ComplianceRadarProps> = ({
  alerts,
  className,
}) => {
  return (
    <div
      role="list"
      data-role="compliance-radar"
      className={
        className ? `compliance-radar ${className}` : "compliance-radar"
      }
      style={ROOT_STYLE}
    >
      {alerts.map((alert, i) => {
        const critical = alert.severity === "critical";
        return (
          <div
            key={alert.id}
            role="listitem"
            data-role="alert-row"
            data-severity={alert.severity}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 11,
              padding: "9px 0",
              borderBottom:
                i < alerts.length - 1
                  ? "1px solid var(--border-default)"
                  : "none",
            }}
          >
            <span
              data-role="severity-dot"
              style={{
                ...DOT_BASE_STYLE,
                background: SEVERITY_DOT[alert.severity],
                boxShadow: critical ? "0 0 9px var(--status-critical)" : "none",
              }}
            />
            <span>
              <span data-role="alert-title" style={TITLE_STYLE}>
                {alert.title}
              </span>
              {alert.detail !== undefined && (
                <span
                  data-role="alert-detail"
                  className="font-mono"
                  style={DETAIL_STYLE}
                >
                  {alert.detail}
                </span>
              )}
            </span>
            {alert.timeLeft !== undefined && (
              <span data-role="alert-when" style={WHEN_STYLE}>
                <span
                  data-role="alert-time-left"
                  className="font-mono"
                  style={critical ? TIME_CRITICAL_STYLE : TIME_BASE_STYLE}
                >
                  {alert.timeLeft}
                </span>
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

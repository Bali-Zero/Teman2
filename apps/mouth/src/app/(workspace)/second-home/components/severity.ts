import type { GuaranteeAlertSeverity } from "@/lib/api/secondhome/secondhome.types";

/** Colors mirror the workspace's shared --state-* tokens (same palette used
 *  by the process board's priority/payment badges). Matches the backend's
 *  `severity_for_days_until` bands: <=7 critical, <=30 urgent, <=60 warning,
 *  else info. */
export function severityColorVar(severity: string): string {
  switch (severity) {
    case "critical":
      return "var(--state-danger)";
    case "urgent":
      return "var(--state-warning)";
    case "warning":
      return "var(--bz-accent)";
    case "info":
    default:
      return "var(--bz-text-2)";
  }
}

export function severityLabel(severity: string): string {
  switch (severity as GuaranteeAlertSeverity) {
    case "critical":
      return "Critical";
    case "urgent":
      return "Urgent";
    case "warning":
      return "Warning";
    case "info":
    default:
      return "Info";
  }
}

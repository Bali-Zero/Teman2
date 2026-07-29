export type CaseStatus =
  | "inquiry"
  | "waiting_documents"
  | "sending_invoice"
  | "on_process"
  | "completed"
  | "unknown";

export type WorkflowStatus = Exclude<CaseStatus, "unknown">;

export interface ColumnColorConfig {
  label: string;
  gradientStart: string;
  gradientEnd: string;
  tintBg: string;
  tintBorder: string;
  badgeBg: string;
  textColor: string;
  dotColor: string;
}

export const COLUMN_COLORS: Record<CaseStatus, ColumnColorConfig> = {
  inquiry: {
    // Neutral intake: status is carried by label + dot, not a loud card.
    label: "Inquiry",
    gradientStart: "var(--bz-text-2)",
    gradientEnd: "var(--bz-text-3)",
    tintBg: "color-mix(in srgb, var(--bz-text-2) 5%, transparent)",
    tintBorder: "color-mix(in srgb, var(--bz-text-2) 18%, transparent)",
    badgeBg: "color-mix(in srgb, var(--bz-text-2) 12%, transparent)",
    textColor: "var(--bz-text-2)",
    dotColor: "bg-[var(--bz-text-2)]",
  },
  waiting_documents: {
    // Waiting is attention, not failure: reserve danger red for blockers.
    label: "Waiting Documents",
    gradientStart: "var(--state-warning)",
    gradientEnd: "var(--state-warning)",
    tintBg: "color-mix(in srgb, var(--state-warning) 5%, transparent)",
    tintBorder: "color-mix(in srgb, var(--state-warning) 22%, transparent)",
    badgeBg: "color-mix(in srgb, var(--state-warning) 12%, transparent)",
    textColor: "var(--state-warning)",
    dotColor: "bg-[var(--state-warning)]",
  },
  sending_invoice: {
    // Copper keeps this commercial step distinct from compliance warnings.
    label: "Sending Invoice",
    gradientStart: "var(--bz-copper-text)",
    gradientEnd: "var(--bz-copper-text)",
    tintBg: "color-mix(in srgb, var(--bz-copper-text) 5%, transparent)",
    tintBorder: "color-mix(in srgb, var(--bz-copper-text) 22%, transparent)",
    badgeBg: "color-mix(in srgb, var(--bz-copper-text) 12%, transparent)",
    textColor: "var(--bz-copper-text)",
    dotColor: "bg-[var(--bz-copper-text)]",
  },
  on_process: {
    label: "On Process",
    gradientStart: "var(--state-info)",
    gradientEnd: "var(--state-info)",
    tintBg: "color-mix(in srgb, var(--state-info) 5%, transparent)",
    tintBorder: "color-mix(in srgb, var(--state-info) 22%, transparent)",
    badgeBg: "color-mix(in srgb, var(--state-info) 12%, transparent)",
    textColor: "var(--state-info)",
    dotColor: "bg-[var(--state-info)]",
  },
  completed: {
    label: "Completed",
    gradientStart: "var(--state-success)",
    gradientEnd: "var(--state-success)",
    tintBg: "color-mix(in srgb, var(--state-success) 4%, transparent)",
    tintBorder: "color-mix(in srgb, var(--state-success) 18%, transparent)",
    badgeBg: "color-mix(in srgb, var(--state-success) 10%, transparent)",
    textColor: "var(--state-success)",
    dotColor: "bg-[var(--state-success)]",
  },
  unknown: {
    // Preserve unexpected backend states visibly instead of silently treating
    // them as intake. They are shown in the board with their raw sub-status.
    label: "Needs Review",
    gradientStart: "var(--state-danger)",
    gradientEnd: "var(--state-warning)",
    tintBg: "color-mix(in srgb, var(--state-danger) 5%, transparent)",
    tintBorder: "color-mix(in srgb, var(--state-danger) 22%, transparent)",
    badgeBg: "color-mix(in srgb, var(--state-danger) 12%, transparent)",
    textColor: "var(--state-danger)",
    dotColor: "bg-[var(--state-danger)]",
  },
};

export const COLUMN_ORDER: WorkflowStatus[] = [
  "inquiry",
  "waiting_documents",
  "sending_invoice",
  "on_process",
  "completed",
];

export function getStatusColumn(status: string): CaseStatus {
  if (status === "inquiry" || status === "request") return "inquiry";
  if (status === "waiting_documents") return "waiting_documents";
  if (status === "sending_invoice") return "sending_invoice";
  if (status === "on_process" || status === "active") return "on_process";
  if (status === "completed" || status === "done") return "completed";
  if (status === "waiting_payment" || status === "payment_pending")
    return "sending_invoice";
  if (
    status === "submitted_to_gov" ||
    status === "approved" ||
    status === "in_progress"
  )
    return "on_process";
  if (
    status === "quotation_sent" ||
    status === "quote" ||
    status === "quotation"
  )
    return "sending_invoice";
  return "unknown";
}

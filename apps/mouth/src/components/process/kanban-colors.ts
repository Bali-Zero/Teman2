export type CaseStatus =
  | "inquiry"
  | "waiting_documents"
  | "sending_invoice"
  | "on_process"
  | "completed";

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
    label: "Inquiry",
    gradientStart: "#6b7280",
    gradientEnd: "#9ca3af",
    tintBg: "rgba(156,163,175, 0.035)",
    tintBorder: "rgba(156,163,175, 0.08)",
    badgeBg: "rgba(156,163,175, 0.12)",
    textColor: "#9ca3af",
    dotColor: "bg-gray-400",
  },
  waiting_documents: {
    label: "Waiting Documents",
    gradientStart: "#fb923c",
    gradientEnd: "#f97316",
    tintBg: "rgba(251,146,60, 0.035)",
    tintBorder: "rgba(251,146,60, 0.08)",
    badgeBg: "rgba(251,146,60, 0.12)",
    textColor: "#fb923c",
    dotColor: "bg-orange-400",
  },
  sending_invoice: {
    label: "Sending Invoice",
    gradientStart: "#facc15",
    gradientEnd: "#eab308",
    tintBg: "rgba(250,204,21, 0.03)",
    tintBorder: "rgba(250,204,21, 0.07)",
    badgeBg: "rgba(250,204,21, 0.12)",
    textColor: "#facc15",
    dotColor: "bg-yellow-400",
  },
  on_process: {
    label: "On Process",
    gradientStart: "#3b82f6",
    gradientEnd: "#2563eb",
    tintBg: "rgba(59,130,246, 0.035)",
    tintBorder: "rgba(59,130,246, 0.08)",
    badgeBg: "rgba(59,130,246, 0.12)",
    textColor: "#3b82f6",
    dotColor: "bg-blue-500",
  },
  completed: {
    label: "Completed",
    gradientStart: "#22c55e",
    gradientEnd: "#16a34a",
    tintBg: "rgba(34,197,94, 0.04)",
    tintBorder: "rgba(34,197,94, 0.09)",
    badgeBg: "rgba(34,197,94, 0.12)",
    textColor: "#22c55e",
    dotColor: "bg-green-500",
  },
};

export const COLUMN_ORDER: CaseStatus[] = [
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
  if (status === "waiting_payment" || status === "payment_pending") return "sending_invoice";
  if (status === "submitted_to_gov" || status === "approved" || status === "in_progress") return "on_process";
  if (status === "quotation_sent" || status === "quote" || status === "quotation") return "sending_invoice";
  return "inquiry";
}

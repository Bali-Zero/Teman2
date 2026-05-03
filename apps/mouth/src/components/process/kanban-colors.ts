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
    // Pastel slate — warm neutral, not cold
    label: "Inquiry",
    gradientStart: "#cbd5e1",
    gradientEnd: "#94a3b8",
    tintBg: "rgba(203,213,225, 0.05)",
    tintBorder: "rgba(203,213,225, 0.12)",
    badgeBg: "rgba(203,213,225, 0.18)",
    textColor: "#cbd5e1",
    dotColor: "bg-slate-300",
  },
  waiting_documents: {
    // Pastel red — was amber, but it collided with Sending Invoice (yellow).
    // Red semantics also fit "action needed from client" → documents missing.
    // Kept pastel (red-300/400) so it doesn't compete with saturated
    // urgent/unpaid badges.
    label: "Waiting Documents",
    gradientStart: "#fca5a5",
    gradientEnd: "#f87171",
    tintBg: "rgba(252,165,165, 0.05)",
    tintBorder: "rgba(252,165,165, 0.12)",
    badgeBg: "rgba(252,165,165, 0.18)",
    textColor: "#fca5a5",
    dotColor: "bg-red-300",
  },
  sending_invoice: {
    // Pastel yellow — softened from the previous harsh yellow-500 to a
    // creamier yellow-300 so it pairs with the rest of the pastel palette.
    label: "Sending Invoice",
    gradientStart: "#fde047",
    gradientEnd: "#facc15",
    tintBg: "rgba(253,224,71, 0.05)",
    tintBorder: "rgba(253,224,71, 0.12)",
    badgeBg: "rgba(253,224,71, 0.18)",
    textColor: "#fde047",
    dotColor: "bg-yellow-300",
  },
  on_process: {
    // Pastel blue — airier than the previous royal blue
    label: "On Process",
    gradientStart: "#93c5fd",
    gradientEnd: "#60a5fa",
    tintBg: "rgba(147,197,253, 0.05)",
    tintBorder: "rgba(147,197,253, 0.12)",
    badgeBg: "rgba(147,197,253, 0.18)",
    textColor: "#93c5fd",
    dotColor: "bg-blue-300",
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
  return "inquiry";
}

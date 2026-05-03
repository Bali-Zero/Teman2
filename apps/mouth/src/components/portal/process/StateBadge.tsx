import type { ProcessStepState } from "@/lib/schemas/process";
import { STATE_COLORS } from "./stateColors";

// Labels — mirror apps/backend-rag/backend/app/routers/portal_process_timeline.py
// STATUS_LABELS verbatim so timeline UI stays consistent with BE-provided
// `step.label` strings. Any update to the BE dict must be reflected here.
const LABELS: Record<ProcessStepState, string> = {
  // Canonical
  inquiry: "Inquiry",
  waiting_documents: "Waiting for Documents",
  sending_invoice: "Sending Invoice",
  on_process: "On Process",
  completed: "Completed",
  cancelled: "Cancelled",
  // Legacy (BE may still echo these from history rows)
  quotation_sent: "Quotation Sent",
  payment_pending: "Payment Pending",
  waiting_payment: "Waiting for Payment",
  in_progress: "In Progress",
  submitted_to_gov: "Submitted to Government",
  approved: "Approved",
};

interface Props {
  state: ProcessStepState;
  /** Optional override (e.g., BE-provided label); falls back to the enum label. */
  label?: string;
}

export function StateBadge({ state, label }: Props) {
  const c = STATE_COLORS[state];
  const text = label ?? LABELS[state];
  return (
    <span
      aria-label={`Status: ${text}`}
      style={{ backgroundColor: c.bg, color: c.fg, borderColor: c.border }}
      className="inline-flex items-center px-2.5 py-1 rounded-full border text-xs font-medium"
    >
      {text}
    </span>
  );
}

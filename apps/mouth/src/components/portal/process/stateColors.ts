// Colors for process timeline states.
// TODO(shared-tokens): --bz-danger is not yet in packages/design-system/tokens/bz-tokens.css.
// When added, the var() fallbacks below will become inert. Track via issue #TODO.
import type { ProcessStepState } from "@/lib/schemas/process";

export interface StateStyle {
  bg: string;
  fg: string;
  border: string;
}

// Semantic groups:
//   neutral  : pending-ish early stages
//   accent   : active / in-progress
//   warning  : waiting-on-client
//   success  : completed / approved
//   danger   : blocked / cancelled
//   invoice  : money-in-flight (distinct from neutral so user notices)
const neutral: StateStyle = {
  bg: "var(--bz-muted-bg, rgba(138,138,142,0.12))",
  fg: "var(--bz-muted-fg, #8a8a8e)",
  border: "var(--bz-muted-fg, #8a8a8e)",
};
const accent: StateStyle = {
  bg: "var(--bz-accent-bg, rgba(212,132,90,0.15))",
  fg: "var(--bz-accent, #d4845a)",
  border: "var(--bz-accent, #d4845a)",
};
const warning: StateStyle = {
  bg: "var(--bz-warning-bg, rgba(201,161,74,0.15))",
  fg: "var(--bz-warning, #c9a14a)",
  border: "var(--bz-warning, #c9a14a)",
};
const success: StateStyle = {
  bg: "var(--bz-success-bg, rgba(74,156,92,0.15))",
  fg: "var(--bz-success, #4a9c5c)",
  border: "var(--bz-success, #4a9c5c)",
};
const danger: StateStyle = {
  bg: "var(--bz-danger-bg, rgba(201,74,74,0.15))",
  fg: "var(--bz-danger, #c94a4a)",
  border: "var(--bz-danger, #c94a4a)",
};
const invoice: StateStyle = {
  bg: "var(--bz-accent-bg, rgba(201,169,110,0.12))",
  fg: "var(--bz-accent, #c9a96e)",
  border: "var(--bz-accent, #c9a96e)",
};

export const STATE_COLORS: Record<ProcessStepState, StateStyle> = {
  // Canonical
  inquiry: neutral,
  waiting_documents: warning,
  sending_invoice: invoice,
  on_process: accent,
  completed: success,
  cancelled: danger,
  // Legacy
  quotation_sent: invoice,
  payment_pending: warning,
  waiting_payment: warning,
  in_progress: accent,
  submitted_to_gov: accent,
  approved: success,
};

// Colors for process timeline states.
// WS3 slice 4 (GARUDA Day Edition, 2026-07-24): fg/border now read the
// semantic --state-* tokens (WS2 operative-light AA overrides are ARMED on
// main via packages/core/tokens/semantic.css — success 4.80:1, warning
// 4.78:1, danger 5.74:1, info 5.94:1 on paper #f4f1ea), replacing the
// never-defined --bz-success/--bz-warning/--bz-danger reads whose hex
// fallbacks failed AA on paper (success #4a9c5c 2.8:1, warning #c9a14a
// 2.1:1). The old --bz-* names are gone; the hexes stay as inert fallbacks.
// Copper (invoice) reads --bz-copper-text with the slice-1 fallback chain
// (var(--bz-copper-text, var(--tx-secondary))) until PR #3050 merges.
import type { ProcessStepState } from "@/lib/schemas/process";

export interface StateStyle {
  bg: string;
  fg: string;
  border: string;
}

// Semantic groups:
//   neutral  : pending-ish early stages
//   info     : active / in-flight (in-progress, submitted to government)
//   warning  : waiting-on-client
//   success  : completed / approved
//   danger   : blocked / cancelled
//   invoice  : money-in-flight (copper, distinct from neutral so user notices)
const neutral: StateStyle = {
  // Border-only chip: transparent bg keeps fg at 4.95:1 on card (a 12%
  // tint would drop it to 4.26:1 — below the 4.5:1 small-text floor).
  bg: "transparent",
  fg: "var(--text-tertiary, #8a8a8e)",
  border: "var(--text-tertiary, #8a8a8e)",
};
const info: StateStyle = {
  bg: "color-mix(in srgb, var(--state-info, #60a5fa) 12%, transparent)",
  fg: "var(--state-info, #1d4ed8)",
  border: "var(--state-info, #1d4ed8)",
};
const warning: StateStyle = {
  bg: "color-mix(in srgb, var(--state-warning, #c9a14a) 12%, transparent)",
  fg: "var(--state-warning, #ad4f08)",
  border: "var(--state-warning, #ad4f08)",
};
const success: StateStyle = {
  bg: "color-mix(in srgb, var(--state-success, #4a9c5c) 12%, transparent)",
  fg: "var(--state-success, #147a3a)",
  border: "var(--state-success, #147a3a)",
};
const danger: StateStyle = {
  bg: "color-mix(in srgb, var(--state-danger, #c94a4a) 12%, transparent)",
  fg: "var(--state-danger, #b91c1c)",
  border: "var(--state-danger, #b91c1c)",
};
const invoice: StateStyle = {
  bg: "color-mix(in srgb, var(--bz-copper-text, var(--tx-secondary, #c9a96e)) 12%, transparent)",
  fg: "var(--bz-copper-text, var(--tx-secondary, #c9a96e))",
  border: "var(--bz-copper-text, var(--tx-secondary, #c9a96e))",
};

export const STATE_COLORS: Record<ProcessStepState, StateStyle> = {
  // Canonical
  inquiry: neutral,
  waiting_documents: warning,
  sending_invoice: invoice,
  on_process: info,
  completed: success,
  cancelled: danger,
  // Legacy
  quotation_sent: invoice,
  payment_pending: warning,
  waiting_payment: warning,
  in_progress: info,
  submitted_to_gov: info,
  approved: success,
};

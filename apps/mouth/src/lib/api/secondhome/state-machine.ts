/**
 * E33 Second Home Case State Machine — Frontend mirror of the backend
 * authority.
 *
 * Source of truth:
 *   apps/backend-rag/backend/services/crm/e33_lifecycle.py
 *   (VALID_TRANSITIONS, TERMINAL_STAGES, E33_ITAP_EVAL_ENABLED)
 *
 * The backend ALWAYS validates transitions (defense-in-depth) — this module
 * only filters the UI dropdown so users do not see illegal options. A case
 * detail response's own `allowed_next_stages` is the authoritative list for
 * rendering the transition control; this file exists so the console can
 * still (a) render a client-side sanity filter and (b) build the create-case
 * "stage" affordances without a round trip. If the two ever diverge, the
 * backend rejects the request and the user sees the existing error toast.
 *
 * ITAP_EVAL is gated behind `E33_ITAP_EVAL_ENABLED = False` on the backend
 * until the letter-006 Q7 written reply (owner decision 2026-07-23). The
 * console must NEVER offer it as a next stage — `getOfferedNextStages`
 * strips it unconditionally, independent of the flag mirror below, so a
 * forgotten flag flip on this side can never re-surface it in the UI.
 */

export type E33StageKey =
  | "fit_memo"
  | "bank_precheck"
  | "application"
  | "payment"
  | "visa_issued"
  | "entry"
  | "itas_active"
  | "guarantee_proof_due"
  | "annual_maintenance"
  | "renewal"
  | "epo"
  | "status_change"
  | "itap_eval";

/**
 * Allowed forward transitions: from → set of valid `to` states.
 * Byte-for-byte mirror of `VALID_TRANSITIONS` in e33_lifecycle.py:97-125.
 */
export const VALID_TRANSITIONS: Record<E33StageKey, readonly E33StageKey[]> = {
  fit_memo: ["bank_precheck"],
  bank_precheck: ["application", "fit_memo"],
  application: ["payment", "bank_precheck"],
  payment: ["visa_issued", "application"],
  visa_issued: ["entry"],
  entry: ["itas_active"],
  itas_active: ["guarantee_proof_due", "epo", "status_change", "itap_eval"],
  guarantee_proof_due: ["annual_maintenance", "epo", "status_change"],
  annual_maintenance: ["renewal", "epo", "status_change", "itap_eval"],
  renewal: ["itas_active"],
  epo: [],
  status_change: [],
  itap_eval: ["status_change"],
} as const;

/** Mirrors `TERMINAL_STAGES` in e33_lifecycle.py. */
export const TERMINAL_STAGES: readonly E33StageKey[] = ["epo", "status_change"];

/** Mirrors `E33_ITAP_EVAL_ENABLED` in e33_lifecycle.py — flip only after the
 *  letter-006 Q7 written reply lands, and only alongside the backend flag. */
export const ITAP_EVAL_ENABLED = false;

/** Human-readable labels for each stage. */
export const STAGE_LABELS: Record<E33StageKey, string> = {
  fit_memo: "Fit Memo",
  bank_precheck: "Bank Pre-check",
  application: "Application",
  payment: "Payment",
  visa_issued: "Visa Issued",
  entry: "Entry",
  itas_active: "ITAS Active",
  guarantee_proof_due: "Guarantee Proof Due",
  annual_maintenance: "Annual Maintenance",
  renewal: "Renewal",
  epo: "EPO (Exit Permit Only)",
  status_change: "Status Change",
  itap_eval: "ITAP Evaluation",
};

export type StageGroup = "pipeline" | "permit" | "terminal";

export const STAGE_GROUP_LABELS: Record<StageGroup, string> = {
  pipeline: "Pipeline",
  permit: "Permit",
  terminal: "Terminal",
};

/**
 * Stage grouping per spec: pipeline = fit_memo…visa_issued, permit =
 * entry/itas_active/guarantee_proof_due/annual_maintenance/renewal,
 * terminal = epo/status_change (+ itap_eval hidden from any group listing).
 */
export const STAGE_GROUP: Record<E33StageKey, StageGroup> = {
  fit_memo: "pipeline",
  bank_precheck: "pipeline",
  application: "pipeline",
  payment: "pipeline",
  visa_issued: "pipeline",
  entry: "permit",
  itas_active: "permit",
  guarantee_proof_due: "permit",
  annual_maintenance: "permit",
  renewal: "permit",
  epo: "terminal",
  status_change: "terminal",
  itap_eval: "terminal",
};

/** Stages in group/pipeline order, EXCLUDING itap_eval — the one stage the
 *  console never lists as a selectable filter or destination. */
export const VISIBLE_STAGES: readonly E33StageKey[] = [
  "fit_memo",
  "bank_precheck",
  "application",
  "payment",
  "visa_issued",
  "entry",
  "itas_active",
  "guarantee_proof_due",
  "annual_maintenance",
  "renewal",
  "epo",
  "status_change",
];

const ALL_STAGES = new Set<string>(Object.keys(VALID_TRANSITIONS));

/**
 * Return the stages the UI may OFFER as a transition target from `current`.
 * Always excludes `itap_eval` (gated feature, never offered regardless of
 * the local `ITAP_EVAL_ENABLED` mirror) and passes unknown/legacy stages
 * through as an empty list (nothing offered until the value is normalized).
 */
export function getOfferedNextStages(
  current: E33StageKey | string,
): E33StageKey[] {
  if (!ALL_STAGES.has(current)) return [];
  return VALID_TRANSITIONS[current as E33StageKey].filter(
    (stage) => stage !== "itap_eval",
  );
}

export function isTerminalStage(stage: E33StageKey | string): boolean {
  return (TERMINAL_STAGES as readonly string[]).includes(stage);
}

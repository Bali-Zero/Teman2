/**
 * Process Timeline Zod Schemas
 *
 * Validates responses from `GET /api/portal/process/{practice_id}/timeline`.
 *
 * Backend source of truth:
 *   apps/backend-rag/backend/app/routers/portal_process_timeline.py
 *
 * State machine source of truth:
 *   apps/backend-rag/backend/services/crm/practice_state_machine.py
 *
 * The state machine defines 6 canonical states (inquiry, waiting_documents,
 * sending_invoice, on_process, completed, cancelled). However, the BE router
 * reads `practice_status_log.new_status` rows which may contain legacy
 * statuses (quotation_sent, payment_pending, waiting_payment, in_progress,
 * submitted_to_gov, approved) — see `LEGACY_STATE_MAP` + `STATUS_LABELS` in
 * the router. The enum therefore covers ALL status strings the BE can emit.
 */

import { z } from "zod";

// ============================================
// STATE ENUM
// ============================================

/**
 * All status strings that may appear in a timeline step.
 *
 * Canonical (current state machine, 6 states):
 *   - inquiry, waiting_documents, sending_invoice, on_process, completed, cancelled
 *
 * Legacy (kept for backward-compat: `portal_process_timeline.py` still maps
 * these from historical activity_log rows; see STATUS_LABELS there. As of
 * 2026-04-20, practices.status in prod contains ONLY canonical values —
 * these legacy names can only appear in timeline steps reconstructed from
 * activity_log history):
 *   - quotation_sent, payment_pending, waiting_payment, in_progress,
 *     submitted_to_gov, approved
 */
export const ProcessStepState = z.enum([
  // Canonical
  "inquiry",
  "waiting_documents",
  "sending_invoice",
  "on_process",
  "completed",
  "cancelled",
  // Legacy (BE may still echo these from history rows)
  "quotation_sent",
  "payment_pending",
  "waiting_payment",
  "in_progress",
  "submitted_to_gov",
  "approved",
]);
export type ProcessStepState = z.infer<typeof ProcessStepState>;

// ============================================
// STEP SCHEMA
// ============================================

/**
 * A single step in the practice timeline.
 *
 * Matches the dict produced by `_build_timeline` in
 * `portal_process_timeline.py`:
 *   - status: str                    → ProcessStepState
 *   - label: str                     → human-readable (e.g. "In Progress")
 *   - completed: bool                → step is done
 *   - is_current: bool               → this is the active step
 *   - changed_at: str | None         → timestamp (stringified by `str(row[...])`)
 *   - changed_by: str | None         → user identifier (may be absent entirely
 *                                      on the single-step fallback path where
 *                                      the dict uses `row.get("changed_by")`)
 */
export const ProcessStep = z.object({
  status: ProcessStepState,
  label: z.string(),
  completed: z.boolean(),
  is_current: z.boolean(),
  changed_at: z.string().nullable().optional(),
  changed_by: z.string().nullable().optional(),
});
export type ProcessStep = z.infer<typeof ProcessStep>;

// ============================================
// TIMELINE DATA (inner)
// ============================================

/**
 * Inner `data` object of the timeline response.
 * Mirrors the dict returned by `_build_timeline`.
 */
export const ProcessTimelineData = z.object({
  practice_id: z.number().int().nonnegative(),
  practice_name: z.string().nullable().optional(),
  practice_category: z.string().nullable().optional(),
  current_status: ProcessStepState,
  assigned_to: z.string().nullable().optional(),
  start_date: z.string().nullable().optional(),
  completion_date: z.string().nullable().optional(),
  expiry_date: z.string().nullable().optional(),
  steps: z.array(ProcessStep),
});
export type ProcessTimelineData = z.infer<typeof ProcessTimelineData>;

// ============================================
// TOP-LEVEL RESPONSE
// ============================================

/**
 * Full response envelope from the endpoint.
 * Shape: `{ "success": true, "data": <ProcessTimelineData> }`
 */
export const ProcessTimelineResponse = z.object({
  success: z.boolean(),
  data: ProcessTimelineData,
});
export type ProcessTimelineResponse = z.infer<typeof ProcessTimelineResponse>;

/**
 * Types for the GARUDA VOA STAFF surface (step 8), reconciled against the
 * real backend contract diff on 2026-09-02: `git -C
 * .worktrees/ops-garuda-voa-step8-portal diff origin/main..HEAD --
 * products/garuda-voa/contracts/openapi.yaml` (that worktree belongs to
 * another agent, read-only). Field names, the list envelope, and error
 * codes below are a byte-accurate transcription of that diff's
 * `listStaffPractices` / `getStaffPractice` / `assignPractice` /
 * `StaffPracticeListItem` / `StaffPracticeView` / `PracticeAssignmentRequest`
 * blocks — no longer this lane's best-effort mirror of the spec prose (see
 * the superseded header comment in git history for the earlier assumption).
 * `transitionPractice`/`PracticeTransitionRequest` were already frozen and
 * unchanged by that diff.
 *
 * Same convention as `visa/voa/orders/types.ts`: no generated client yet.
 */

import type { PracticeState } from "@/app/visa/voa/orders/types";

export type { PracticeState };

/** `StaffPracticeListItem` (openapi.yaml) — deliberately thin: no customer
 * PII beyond what the contract explicitly allows, no `private_staff_note`.
 * `customer_reason_key`/`required_action_key` are `oneOf [null, string]` and
 * NOT in the schema's `required` list — optional AND nullable on the wire. */
export interface StaffPracticeListRow {
  practice_id: string;
  order_id: string;
  state: PracticeState;
  assigned_to: string | null;
  updated_at: string;
  customer_reason_key?: string | null;
  required_action_key?: string | null;
  artifact_available: boolean;
}

/** `listStaffPractices` 200 body — `{ items, next_cursor }`, NOT
 * `{ practices, cursor }` (corrected 2026-09-02 against the real diff). */
export interface StaffPracticeListResponse {
  items: StaffPracticeListRow[];
  next_cursor: string | null;
}

/** `StaffPracticeView` (openapi.yaml) — a superset of `StaffPracticeListItem`
 * carrying `private_staff_note` and `resume_target`. Never reused by a
 * customer-facing schema (contract note: PR-F04).
 *
 * `active_block_id`, `artifact_id`, `artifact_digest` are NOT in the
 * openapi.yaml diff read 2026-09-02 — the backend's round 2 will add them
 * (per team-lead relay). Kept optional here so this lane compiles against
 * both the current and the round-2 contract without another edit; treat a
 * missing `active_block_id` as "no active block on record" (see
 * [practiceId]/page.tsx's read-only resume-id field). */
export interface StaffPracticeView extends StaffPracticeListRow {
  private_staff_note: string | null;
  resume_target: PracticeState | null;
  active_block_id?: string | null;
  artifact_id?: string | null;
  artifact_digest?: string | null;
}

/** `PracticeAssignmentRequest` (openapi.yaml) — `assigned_to` required,
 * `null` unassigns. */
export interface AssignPracticeRequest {
  assigned_to: string | null;
}

/** `PracticeTransitionRequest` (openapi.yaml, frozen, unchanged by the
 * 2026-09-02 diff) — one variant per PR-02..PR-11. Discriminated on
 * `transition_id`. */
export type PracticeTransitionRequest =
  | { transition_id: "PR-02" }
  | {
      transition_id: "PR-03" | "PR-05" | "PR-08";
      customer_reason_key: string;
      required_action_key: string;
      private_staff_note?: string;
    }
  | { transition_id: "PR-04"; evidence_id: string }
  | { transition_id: "PR-06"; evidence_id: string }
  | {
      transition_id: "PR-07";
      evidence_id: string;
      customer_reason_key: string;
      private_staff_note?: string;
    }
  | { transition_id: "PR-09" | "PR-10"; resolved_block_id: string }
  | { transition_id: "PR-11"; artifact_id: string; artifact_digest: string };

export type TransitionId = PracticeTransitionRequest["transition_id"];

/** Customer-facing shape returned by `transitionPractice` — reuse the
 * existing `PracticeView` contract type, never a second definition. */
export type { PracticeView } from "@/app/visa/voa/orders/types";

/** Closed error catalog — union of `x-error-codes` across all five staff
 * operations in the openapi.yaml diff (listStaffPractices,
 * getStaffPractice, assignPractice, transitionPractice — the fifth,
 * late-resolution, is not consumed by this lane). Unlisted codes are still
 * handled (see api-client.ts) as a generic retryable failure. */
export type StaffErrorCode =
  | "IDEMPOTENCY_KEY_REQUIRED"
  | "SESSION_REQUIRED"
  | "ACCESS_DENIED"
  | "GARUDA_PUBLIC_DISABLED"
  | "PRACTICE_NOT_FOUND"
  | "IDEMPOTENCY_CONFLICT"
  | "INVALID_STATE_TRANSITION"
  | "INVALID_REQUEST"
  | "SERVICE_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface StaffErrorResponse {
  code: StaffErrorCode;
  retryable: boolean;
  message_key: string;
}

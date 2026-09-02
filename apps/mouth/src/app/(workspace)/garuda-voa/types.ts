/**
 * Hand-written types for the GARUDA VOA STAFF surface (step 8). Mirrors the
 * three NEW staff operations from `docs plans` step8 spec
 * (`listStaffPractices`, `getStaffPractice`, `assignPractice`) plus the
 * FROZEN `transitionPractice` contract already declared in
 * `products/garuda-voa/contracts/openapi.yaml`.
 *
 * `listStaffPractices`/`getStaffPractice`/`assignPractice` are NOT yet in the
 * frozen openapi.yaml as of this lane's build — the backend PR (Deliverable
 * A, built in parallel) adds them in the same step. This file is a hand
 * mirror of the step8-spec.md contract description, not a transcription of
 * an existing YAML block — verify against the merged openapi.yaml before
 * trusting field names blindly on the next touch of this file.
 *
 * Same convention as `visa/voa/orders/types.ts`: no generated client yet.
 */

import type { PracticeState } from "@/app/visa/voa/orders/types";

export type { PracticeState };

/** Rows returned by `GET /api/visa/voa/staff/practices` — deliberately thin:
 * no customer PII beyond what the spec explicitly allows, no
 * `private_staff_note`. */
export interface StaffPracticeListRow {
  practice_id: string;
  order_id: string;
  state: PracticeState;
  assigned_to: string | null;
  updated_at: string;
  customer_reason_key?: string;
  required_action_key?: string;
  artifact_available: boolean;
}

export interface StaffPracticeListResponse {
  practices: StaffPracticeListRow[];
  cursor: string | null;
}

/** Staff-only detail view — distinct schema from the customer-facing
 * `PracticeView` (orders/types.ts). Never reuse one for the other: the
 * customer shape must never carry `private_staff_note`/`resume_target`.
 *
 * `active_block_id` (added post cross-family review, binding): the opaque id
 * of the CURRENTLY open block on this practice, when `state === "Blocked"`.
 * The resume transitions (PR-09/PR-10) MUST send this exact value as
 * `resolved_block_id` — the UI prefills it read-only, it is never a
 * free-text field a staffer types (see [practiceId]/page.tsx). */
export interface StaffPracticeView extends StaffPracticeListRow {
  private_staff_note: string | null;
  resume_target: PracticeState | null;
  active_block_id: string | null;
}

export interface AssignPracticeRequest {
  assigned_to: string | null;
}

/** `PracticeTransitionRequest` (openapi.yaml, frozen) — one variant per
 * PR-02..PR-11. Discriminated on `transition_id`. */
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

/** Closed error catalog — union of `x-error-codes` across the four staff
 * operations (transitionPractice frozen; the other three are this lane's
 * best-effort mirror of the spec's described responses). Unlisted codes are
 * still handled (see api-client.ts) as a generic retryable failure. */
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

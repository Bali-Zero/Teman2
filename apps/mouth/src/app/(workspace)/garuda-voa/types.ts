/**
 * Types for the GARUDA VOA STAFF surface. Staff read models derive from
 * the generated frozen product contract, preserving optional and nullable
 * wire fields. Request and error types retain their existing public API.
 */

import type { PracticeState } from "@/app/visa/voa/orders/types";
import type { components, operations } from "@/lib/api/garuda-voa.generated";

export type { PracticeState };

/** `StaffPracticeListItem` (openapi.yaml) — deliberately thin: no customer
 * PII beyond what the contract explicitly allows, no `private_staff_note`.
 * `customer_reason_key`/`required_action_key` are `oneOf [null, string]` and
 * NOT in the schema's `required` list — optional AND nullable on the wire. */
export type StaffPracticeListRow =
  components["schemas"]["StaffPracticeListItem"];

/** `listStaffPractices` 200 body — `{ items, next_cursor }`, NOT
 * `{ practices, cursor }` (corrected 2026-09-02 against the real diff). */
export type StaffPracticeListResponse =
  operations["listStaffPractices"]["responses"][200]["content"]["application/json"];

/** `StaffPracticeView` (openapi.yaml) — a superset of `StaffPracticeListItem`
 * carrying `private_staff_note` and `resume_target`. Never reused by a
 * customer-facing schema (contract note: PR-F04).
 *
 * Note, resume target and artifact metadata retain the contract's optional
 * fields. Treat a missing `active_block_id` as "no active block on record" (see
 * [practiceId]/page.tsx's read-only resume-id field). */
export type StaffPracticeView = components["schemas"]["StaffPracticeView"];

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

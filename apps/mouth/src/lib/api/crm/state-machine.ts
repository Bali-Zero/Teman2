/**
 * Practice State Machine — Frontend mirror of the backend authority.
 *
 * Source of truth:
 *   apps/backend-rag/backend/services/crm/practice_state_machine.py
 *
 * The backend ALWAYS validates transitions (defense-in-depth). This module
 * only filters the UI dropdown so users do not see illegal options. If the
 * two ever diverge, the backend rejects the request and the user sees the
 * existing error toast — data stays consistent. The snapshot test in
 * `state-machine.test.ts` pins the table; if the backend changes, that
 * test fails and the discrepancy is caught in CI.
 */

export type PracticeStatus =
  | "inquiry"
  | "waiting_documents"
  | "sending_invoice"
  | "on_process"
  | "completed"
  | "cancelled";

/**
 * Allowed forward transitions: from → set of valid `to` states.
 * Mirrors `VALID_TRANSITIONS` in the backend module.
 */
export const VALID_TRANSITIONS: Record<PracticeStatus, readonly PracticeStatus[]> = {
  inquiry: ["waiting_documents", "cancelled"],
  waiting_documents: ["sending_invoice", "inquiry", "cancelled"],
  sending_invoice: ["on_process", "waiting_documents", "cancelled"],
  on_process: ["completed", "sending_invoice", "cancelled"],
  completed: ["cancelled"],
  cancelled: ["inquiry"],
} as const;

/**
 * Transitions that require an admin role on the user object.
 * Mirrors `ADMIN_ONLY_TRANSITIONS` in the backend module.
 */
export const ADMIN_ONLY_TRANSITIONS: ReadonlyArray<readonly [PracticeStatus, PracticeStatus]> = [
  ["completed", "cancelled"],
  ["cancelled", "inquiry"],
] as const;

/** Human-readable labels for each state. */
export const STATUS_LABELS: Record<PracticeStatus, string> = {
  inquiry: "Inquiry",
  waiting_documents: "Waiting Documents",
  sending_invoice: "Sending Invoice",
  on_process: "On Process",
  completed: "Completed",
  cancelled: "Cancelled",
};

const ALL_STATES = new Set<string>(Object.keys(VALID_TRANSITIONS));

/**
 * Return the list of states the user can transition INTO from `current`,
 * including `current` itself (so the dropdown can keep its existing
 * selection without flagging it as illegal).
 *
 * Admin-only transitions are filtered out when `isAdmin` is false.
 *
 * Unknown / legacy states pass through unchanged: only `current` is
 * returned, so the user can keep the value but cannot move to anything
 * else without first hitting a known state via the backend's normalize
 * step.
 */
export function getAllowedNextStatuses(
  current: PracticeStatus | string,
  isAdmin: boolean = false,
): PracticeStatus[] {
  if (!ALL_STATES.has(current)) {
    return [current as PracticeStatus];
  }

  const next: PracticeStatus[] = [current as PracticeStatus];
  for (const candidate of VALID_TRANSITIONS[current as PracticeStatus]) {
    if (
      !isAdmin &&
      ADMIN_ONLY_TRANSITIONS.some(
        ([from, to]) => from === current && to === candidate,
      )
    ) {
      continue;
    }
    next.push(candidate);
  }
  return next;
}

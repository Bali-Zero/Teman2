/**
 * The allowed next transitions for each `PracticeState`, transcribed from
 * `journeys/STATE-MACHINE.md` rows PR-02..PR-11 (step8-contract.md, this
 * lane's ground). The DB trigger `guard_garuda_practice_state_transition` is
 * the actual authority — this table exists so the UI never renders a button
 * the trigger would reject, never so the UI can skip asking the server.
 *
 * `"In review"` (with a space) is pinned against the real backend contract —
 * verified 2026-09-02 against `products/garuda-voa/contracts/openapi.yaml`'s
 * `PracticeState` enum (`[Received, "In review", Blocked, Submitted,
 * Approved, Rejected, Delivered]`), NOT the DB column's `In_review` spelling.
 * See `state-machine.test.ts` for the pinning test.
 *
 * PR-09/PR-10 (resume from Blocked) both use the same source state
 * (`Blocked`) but resolve to a different target depending on the stored
 * `resume_target` on the practice — so `Blocked` is handled specially by the
 * caller (see [practiceId]/page.tsx), not through this static table alone.
 */

import type { PracticeState, TransitionId } from "./types";

export interface TransitionOption {
  transitionId: TransitionId;
  label: string;
  targetState: PracticeState;
}

const RECEIVED: TransitionOption[] = [
  { transitionId: "PR-02", label: "Begin review", targetState: "In review" },
  {
    transitionId: "PR-03",
    label: "Block (needs customer action)",
    targetState: "Blocked",
  },
];

const IN_REVIEW: TransitionOption[] = [
  { transitionId: "PR-04", label: "Submit filing", targetState: "Submitted" },
  {
    transitionId: "PR-05",
    label: "Block (needs customer action)",
    targetState: "Blocked",
  },
];

const SUBMITTED: TransitionOption[] = [
  { transitionId: "PR-06", label: "Approve", targetState: "Approved" },
  { transitionId: "PR-07", label: "Reject", targetState: "Rejected" },
  {
    transitionId: "PR-08",
    label: "Block (needs customer action)",
    targetState: "Blocked",
  },
];

const APPROVED: TransitionOption[] = [
  {
    transitionId: "PR-11",
    label: "Deliver artifact",
    targetState: "Delivered",
  },
];

/** `Blocked` resolves via PR-09 (-> In review) or PR-10 (-> Submitted)
 * depending on the practice's stored `resume_target`. Both options are
 * listed here; the caller filters to the one matching `resume_target` and
 * treats a missing/unrecognized `resume_target` as "no resume available"
 * (never guess which target the DB trigger will accept). */
const BLOCKED: TransitionOption[] = [
  { transitionId: "PR-09", label: "Resume review", targetState: "In review" },
  {
    transitionId: "PR-10",
    label: "Resume submission",
    targetState: "Submitted",
  },
];

const TERMINAL: TransitionOption[] = [];

const TRANSITIONS_BY_STATE: Record<PracticeState, TransitionOption[]> = {
  Received: RECEIVED,
  "In review": IN_REVIEW,
  Blocked: BLOCKED,
  Submitted: SUBMITTED,
  Approved: APPROVED,
  Rejected: TERMINAL,
  Delivered: TERMINAL,
};

/** Returns the transitions the CURRENT state allows. For `Blocked`, pass
 * `resumeTarget` (the practice's stored resume target) to narrow PR-09/PR-10
 * down to the single option the DB trigger will actually accept. */
export function getAllowedTransitions(
  state: PracticeState,
  resumeTarget?: PracticeState | null,
): TransitionOption[] {
  if (state !== "Blocked") return TRANSITIONS_BY_STATE[state];
  if (!resumeTarget) return [];
  return BLOCKED.filter((option) => option.targetState === resumeTarget);
}

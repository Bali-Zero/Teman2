/**
 * CRM-18 — who is OFFERED the delete action.
 *
 * The button is an offer, never the fence. The fence is
 * `verify_client_access(client_id, current_user, conn, allow_assigned=True,
 * write=True)` in apps/backend-rag/backend/app/utils/crm_utils.py:169-232,
 * reached from `delete_client` (crm_clients.py:1814-1836): admin passes
 * always, a non-admin passes only on `assigned_to` or `created_by`.
 * "Admin" on the desk is the role intersection of frontend and backend:
 * admin, founder.
 *
 * This guard pins the OFFER to the half of that rule the desk can actually
 * see, and it proves guilt as well as innocence — a predicate that only ever
 * returned true would pass an innocence-only suite while handing every
 * viewer a button that 403s.
 *
 * The narrowing is deliberate and is itself pinned below: the profile
 * payload (crm_enhanced.py:1040-1053) carries `assigned_to` but NOT
 * `created_by`, so a non-admin creator gets no button. Erring narrow means a
 * missing button, never a button that fails.
 */
import { describe, it, expect } from "vitest";
import { viewerCanDeleteClient } from "../../client-row-model";

const VIEWER = "staff@balizero.com";
const OTHER = "someone.else@balizero.com";

const clientAssignedTo = (assigned_to?: string) => ({ assigned_to });

describe("viewerCanDeleteClient — innocence", () => {
  it("offers the action to an admin, whoever the record is assigned to", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, "admin"),
    ).toBe(true);
  });

  it("offers the action to an admin on an unassigned record", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(undefined), VIEWER, "admin"),
    ).toBe(true);
  });

  it("offers the action to a founder, and folds role case/space", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, " Founder "),
    ).toBe(true);
  });

  it("offers the action to the assigned non-admin", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(VIEWER), VIEWER, "staff"),
    ).toBe(true);
  });

  it("matches the backend's case/space folding on both sides", () => {
    expect(
      viewerCanDeleteClient(
        clientAssignedTo("  Staff@BaliZero.com "),
        " STAFF@balizero.COM ",
        "staff",
      ),
    ).toBe(true);
  });
});

describe("viewerCanDeleteClient — guilt", () => {
  it("does NOT offer the action to a non-admin who is not assigned", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, "staff"),
    ).toBe(false);
  });

  it("does NOT offer the action on an unassigned record to a non-admin", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(undefined), VIEWER, "staff"),
    ).toBe(false);
  });

  it("does NOT offer the action while the viewer is unknown", () => {
    // `currentUserEmail` is "" until the profile read resolves. An empty
    // viewer must never match an empty `assigned_to`, or every record with no
    // owner would hand its button to everybody during first paint.
    expect(
      viewerCanDeleteClient(clientAssignedTo(undefined), "", "staff"),
    ).toBe(false);
    expect(viewerCanDeleteClient(clientAssignedTo(""), "", "staff")).toBe(
      false,
    );
  });

  it("does NOT offer the admin path to owner or board when not assigned", () => {
    // `api.isAdmin()` (lib/api/client.ts:301-308) counts owner and board as
    // admin; the backend's is_crm_admin (crm_utils.py:108-118) does not, so
    // an unassigned owner/board viewer would get a 403 behind the button.
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, "owner"),
    ).toBe(false);
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, "board"),
    ).toBe(false);
  });

  it("does NOT offer the action when the role is unknown", () => {
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, undefined),
    ).toBe(false);
  });

  it("stays narrower than the backend: creator-but-not-assigned gets nothing", () => {
    // The backend would let this viewer through on `created_by`. The profile
    // response does not carry that field, so the desk cannot see it and
    // declines to guess. Widening this needs the backend to send it first.
    expect(
      viewerCanDeleteClient(clientAssignedTo(OTHER), VIEWER, "staff"),
    ).toBe(false);
  });
});

describe("viewerCanDeleteClient is not the attention predicate", () => {
  it("does not lapse when the record stops moving", () => {
    // `viewerIsNext` gates on MOVING_CLIENT_STATUSES; permission does not.
    // A completed record assigned to the viewer is still theirs to delete.
    expect(
      viewerCanDeleteClient(clientAssignedTo(VIEWER), VIEWER, "staff"),
    ).toBe(true);
  });
});

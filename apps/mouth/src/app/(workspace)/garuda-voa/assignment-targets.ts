/**
 * The GARUDA assignee picker's data source:
 * `GET /api/crm/garuda/assignment-targets`.
 *
 * Replaces `useTeamMemberOptions()` (the shared CRM roster,
 * `GET /api/team/members`) on the staff practice detail page. The roster is a
 * VISIBILITY artifact filtered by the role denylist `{client, monitoring}`,
 * while `assignPractice` refuses more than that — an active row whose email is
 * in `PRACTICES_EXTRA_VIEW_EMAILS` (the read-only accounting full view) and any
 * `partner` row — so the picker offered options whose only possible outcome was
 * a 422. The endpoint answers with exactly the emails the gate accepts, asked
 * of that gate rather than copied from it, so the picker and the 422 cannot
 * drift apart again when the role rule changes.
 *
 * Deliberately NOT in `./types` or `./api-client.ts`: those wrap the four
 * operations of the frozen GARUDA VOA contract
 * (`products/garuda-voa/contracts/openapi.yaml`), and this endpoint is
 * CRM-side, exactly like the roster it replaces. It keeps that file's transport
 * convention though — same-origin `fetch` with `credentials: "same-origin"`,
 * never `NEXT_PUBLIC_API_URL`, which would drop the httpOnly session cookie and
 * the Next.js proxy's CSRF promotion (see `api-client.ts`'s header comment for
 * the live 401 that taught it).
 */

import { useQuery } from "@tanstack/react-query";

export interface GarudaAssignmentTarget {
  email: string;
  label: string;
}

const ASSIGNMENT_TARGETS_URL = "/api/crm/garuda/assignment-targets";

/** Thrown when the picker's source is unreachable, refuses the caller, or
 * answers something that is not the `{items: [...]}` shape. Mirrors
 * `api-client.ts::GarudaStaffUnexpectedError`, including the `sourceCause`
 * spelling (an `Error` `cause` is not part of this app's TS lib target). */
export class AssignmentTargetsError extends Error {
  public readonly sourceCause: unknown;

  constructor(
    public readonly httpStatus: number | null,
    cause?: unknown,
  ) {
    super(`AssignmentTargetsError(${httpStatus})`);
    this.name = "AssignmentTargetsError";
    this.sourceCause = cause;
  }
}

function isTarget(value: unknown): value is GarudaAssignmentTarget {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<GarudaAssignmentTarget>;
  return (
    typeof candidate.email === "string" && typeof candidate.label === "string"
  );
}

export async function fetchAssignmentTargets(
  signal?: AbortSignal,
): Promise<GarudaAssignmentTarget[]> {
  let response: Response;
  try {
    response = await fetch(ASSIGNMENT_TARGETS_URL, {
      method: "GET",
      credentials: "same-origin",
      signal,
    });
  } catch (cause) {
    throw new AssignmentTargetsError(null, cause);
  }
  if (!response.ok) throw new AssignmentTargetsError(response.status);

  let body: unknown;
  try {
    body = await response.json();
  } catch (cause) {
    throw new AssignmentTargetsError(response.status, cause);
  }
  const items = (body as { items?: unknown } | null)?.items;
  if (!Array.isArray(items)) throw new AssignmentTargetsError(response.status);
  return items.filter(isTarget);
}

/** `enabled` is the page's own admin flag. A non-admin staff member gets a 403
 * from this endpoint (they cannot assign a practice, so they are not sent the
 * list of people to assign one to) — the query simply never runs for them, and
 * the page does not render the picker either. */
export function useGarudaAssignmentTargets(enabled: boolean) {
  return useQuery({
    queryKey: ["garuda", "assignment-targets"],
    queryFn: ({ signal }) => fetchAssignmentTargets(signal),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

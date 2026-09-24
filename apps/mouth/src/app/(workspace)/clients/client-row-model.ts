/**
 * K3a row model for the /clients desk — SAETTA-R19K window K3.
 *
 * Pure, dependency-free besides the r19 `PillTone` type: no React, no hooks,
 * no clock read of its own — every function that needs "now" takes it as an
 * explicit argument so a test stays deterministic.
 *
 * `fusion/concept.md` §3 splits the four colour meanings from a SEPARATE
 * ownership axis: a status string never resolves to "you" on its own.
 * `fusion/DISPOSITION-fusion.md`:
 *   F3  — a date is urgency, never ownership. The passport/contact tones
 *         below are "warning" or "muted", never copper.
 *   F6  — the copper ordinal must clear the instant a record leaves the
 *         queue, so ownership is re-derived from the live status, never
 *         cached alongside it.
 *   F15 — a terminal record (completed/lost/inactive) can never need the
 *         viewer, even when it is still assigned to them.
 */

import type { PillTone } from "@/components/workspace/r19";
import type { Client } from "@/lib/api/crm/crm.types";

const DAY_MS = 86_400_000;

/** completed | lost | inactive — a record nobody is waiting on the viewer for. */
export function isTerminalClientStatus(status: string): boolean {
  return status === "completed" || status === "lost" || status === "inactive";
}

/**
 * concept-K v2 §3. lead -> wait, active -> ours, completed -> ok,
 * lost -> wait, inactive -> wait. Unknown -> wait.
 * NOTE: `you` is never returned from a status. Ownership is a separate axis.
 */
export function clientStatusTone(status: string): PillTone {
  switch (status) {
    case "active":
      return "ours";
    case "completed":
      return "ok";
    default:
      return "wait";
  }
}

/**
 * The statuses that can still be waiting on somebody. An ALLOW-list, not the
 * complement of the terminal list: copper has to be PROVEN, and a status this
 * model does not recognise proves nothing. The earlier deny-list shape
 * (`!isTerminalClientStatus`) failed OPEN — an unknown or future status on a
 * record assigned to the viewer painted copper and claimed they were next.
 * r19/README.md law 1: where ownership is not derivable, use `wait`.
 */
const MOVING_CLIENT_STATUSES = new Set(["lead", "active"]);

/**
 * The ownership predicate. TRUE only when the viewer is assigned AND the
 * record carries a status this model knows is still moving. A terminal record
 * can never need the viewer (fusion DISPOSITION F15), a date can never make it
 * copper (F3), and an unrecognised status can never make it copper either.
 */
export function viewerIsNext(
  client: Pick<Client, "assigned_to" | "status">,
  viewerEmail: string,
): boolean {
  if (!viewerEmail || !client.assigned_to) return false;
  if (client.assigned_to !== viewerEmail) return false;
  return MOVING_CLIENT_STATUSES.has(client.status);
}

/**
 * May this viewer soft-delete this client?
 *
 * Mirrors the backend rule `verify_client_access(..., write=True)`
 * (apps/backend-rag/backend/app/utils/crm_utils.py:169-232): admins always
 * pass; a non-admin passes when their email matches `assigned_to` OR
 * `created_by`.
 *
 * "Admin" here is NOT `api.isAdmin()`. That method (lib/api/client.ts:301-308)
 * accepts roles admin|founder|owner|board; the backend's `is_crm_admin`
 * (crm_utils.py:108-118) accepts admin|board member|ceo|founder plus email
 * allowlists the desk cannot see. Only the INTERSECTION of the two role sets
 * is offered the admin path, so an owner/board viewer the backend would 403
 * sees no button. The profile payload
 * (crm_enhanced.py:1040-1053) does NOT carry `created_by`, so this predicate
 * can only see the `assigned_to` half and is deliberately NARROWER than the
 * backend: a non-admin creator who is not also assigned sees no button, and
 * the button that IS shown never leads to a 403. Widening it needs
 * `created_by` on the profile response first — a backend change, out of scope
 * for CRM-18.
 *
 * Distinct from `viewerIsNext`, which is a status-gated ATTENTION predicate:
 * permission does not lapse when a record stops moving.
 */
const DELETE_ADMIN_ROLES: ReadonlySet<string> = new Set(["admin", "founder"]);

export function viewerCanDeleteClient(
  client: Pick<Client, "assigned_to">,
  viewerEmail: string,
  viewerRole: string | undefined,
): boolean {
  if (DELETE_ADMIN_ROLES.has((viewerRole ?? "").trim().toLowerCase())) {
    return true;
  }
  const viewer = viewerEmail.trim().toLowerCase();
  const assigned = (client.assigned_to ?? "").trim().toLowerCase();
  if (!viewer || !assigned) return false;
  return assigned === viewer;
}

/** Whole days until the passport expires; negative when expired; null when unset. */
export function passportDaysLeft(
  expiry: string | undefined,
  now: number,
): number | null {
  if (!expiry) return null;
  const expiryMs = new Date(expiry).getTime();
  if (Number.isNaN(expiryMs)) return null;
  return Math.floor((expiryMs - now) / DAY_MS);
}

/** "warning" when expired or within 90 days, else "muted". NEVER "you", never danger. */
export function passportTone(daysLeft: number | null): "warning" | "muted" {
  if (daysLeft === null) return "muted";
  return daysLeft <= 90 ? "warning" : "muted";
}

/** Short label: "exp 12d ago" | "expires today" | "45d" | "14mo" | "—". */
export function passportLabel(daysLeft: number | null): string {
  if (daysLeft === null) return "—";
  if (daysLeft < 0) return `exp ${Math.abs(daysLeft)}d ago`;
  if (daysLeft === 0) return "expires today";
  if (daysLeft < 60) return `${daysLeft}d`;
  return `${Math.round(daysLeft / 30)}mo`;
}

/** Whole days since last interaction; null when never. */
export function lastContactAgeDays(
  date: string | undefined,
  now: number,
): number | null {
  if (!date) return null;
  const contactMs = new Date(date).getTime();
  if (Number.isNaN(contactMs)) return null;
  return Math.floor((now - contactMs) / DAY_MS);
}

/** "Today" | "1d ago" | "5d ago" | "3w ago" | "7mo ago" | "—" */
export function lastContactLabel(ageDays: number | null): string {
  if (ageDays === null) return "—";
  if (ageDays <= 0) return "Today";
  if (ageDays === 1) return "1d ago";
  if (ageDays < 7) return `${ageDays}d ago`;
  if (ageDays < 30) return `${Math.floor(ageDays / 7)}w ago`;
  return `${Math.floor(ageDays / 30)}mo ago`;
}

/** "warning" when 30+ days silent or never contacted, else "muted". No green, no red. */
export function lastContactTone(ageDays: number | null): "warning" | "muted" {
  if (ageDays === null) return "warning";
  return ageDays >= 30 ? "warning" : "muted";
}

export interface DeskCounts {
  total: number;
  needsYou: number;
}

/**
 * Counts over the rows currently in view. `needsYou` uses viewerIsNext, so it
 * is the ONE derived number the desk shows in copper. Caller passes the rows
 * with any optimistic status already applied, which is what makes the copper
 * count clear the instant a row leaves the queue.
 */
export function deskCounts(clients: Client[], viewerEmail: string): DeskCounts {
  let total = 0;
  let needsYou = 0;
  for (const client of clients) {
    total += 1;
    if (viewerIsNext(client, viewerEmail)) needsYou += 1;
  }
  return { total, needsYou };
}

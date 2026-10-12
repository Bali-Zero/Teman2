import type { PortalMatter } from "@/lib/api/portal/portal.types";

/** A practice is active unless it is finished or called off. */
const INACTIVE_STATUSES = new Set(["completed", "cancelled"]);

export function isActiveMatter(matter: Pick<PortalMatter, "status">): boolean {
  return !INACTIVE_STATUSES.has((matter.status ?? "").trim().toLowerCase());
}

export function activeMatters<T extends Pick<PortalMatter, "status">>(
  matters: readonly T[],
): T[] {
  return matters.filter(isActiveMatter);
}

/**
 * `undefined` = the client has not touched the picker yet. The only default
 * is the single active practice, and the picker always renders it — it is
 * never applied behind the client's back.
 */
export type UploadPracticeChoice = string | null | undefined;

export function resolveUploadPractice(
  active: readonly Pick<PortalMatter, "id">[],
  choice: UploadPracticeChoice,
): string | null {
  if (
    choice === null ||
    (choice !== undefined && active.some((m) => String(m.id) === choice))
  )
    return choice;
  return active.length === 1 ? String(active[0].id) : null;
}

/** 2+ active practices: the client must pick one before uploading. */
export function uploadNeedsPractice(
  active: readonly unknown[],
  resolved: string | null,
): boolean {
  return active.length >= 2 && resolved === null;
}

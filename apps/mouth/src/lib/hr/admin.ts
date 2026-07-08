/**
 * HR admin check.
 *
 * MUST stay in sync with backend `hr_utils.HR_ADMIN_EMAILS`
 * (apps/backend-rag/backend/app/utils/hr_utils.py).
 *
 * The frontend uses this only to gate UI elements (admin tabs, settings,
 * employees page). The real authorization happens server-side via
 * `is_hr_admin()` on every HR endpoint, so a misconfigured frontend cannot
 * grant access — at worst it hides admin controls from a real admin.
 */

const HR_ADMIN_EMAILS: ReadonlySet<string> = new Set([
  "zero@balizero.com",
  "antonellosiano@gmail.com",
  "asya@balizero.com",
  "ruslana@balizero.com",
]);

export function isHRAdmin(profile: { email?: string; role?: string } | null | undefined): boolean {
  if (!profile) return false;
  const email = profile.email?.toLowerCase() ?? "";
  if (HR_ADMIN_EMAILS.has(email)) return true;
  return profile.role === "admin";
}

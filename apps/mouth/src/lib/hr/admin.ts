/**
 * HR admin check.
 *
 * MUST stay in sync with backend `hr_utils.is_hr_admin` / `HR_EXTRA_ADMIN_EMAILS`
 * (apps/backend-rag/backend/app/utils/hr_utils.py), which unions the global
 * admin allowlist (`settings.admin_emails_set`) with HR-specific extras.
 *
 * The frontend uses this only to gate UI elements (admin tabs, settings,
 * employees page). The real authorization happens server-side via
 * `is_hr_admin()` on every HR endpoint, so a misconfigured frontend cannot
 * grant access — at worst it hides admin controls from a real admin.
 */

import { GLOBAL_ADMIN_EMAILS } from "@/lib/auth/owner";

// HR-specific additions on top of GLOBAL_ADMIN_EMAILS — mirrors backend
// HR_EXTRA_ADMIN_EMAILS (Ruslana is HR-admin only, not a global admin).
const HR_EXTRA_ADMIN_EMAILS: ReadonlySet<string> = new Set(["ruslana@balizero.com"]);

const HR_ADMIN_EMAILS: ReadonlySet<string> = new Set([
  ...GLOBAL_ADMIN_EMAILS,
  ...HR_EXTRA_ADMIN_EMAILS,
]);

export function isHRAdmin(profile: { email?: string; role?: string } | null | undefined): boolean {
  if (!profile) return false;
  const email = profile.email?.toLowerCase() ?? "";
  if (HR_ADMIN_EMAILS.has(email)) return true;
  return profile.role === "admin";
}

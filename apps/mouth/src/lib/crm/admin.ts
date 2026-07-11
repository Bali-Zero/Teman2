/**
 * CRM admin check (frontend, UI-gating only).
 *
 * MUST stay loosely in sync with backend `crm_utils.CRM_EXTRA_ADMIN_EMAILS`
 * + the global admin allowlist + role==='admin'
 * (apps/backend-rag/backend/app/utils/crm_utils.py::is_crm_admin).
 *
 * This is used ONLY to hide/show UI affordances (the Accounting command-palette
 * shortcut, admin-only buttons). Real authorization happens server-side on every
 * /api/crm/accounting/* endpoint via is_crm_admin() → 403 otherwise, so a
 * misconfigured frontend can never grant access — at worst it hides a control
 * from a real admin.
 */

import { GLOBAL_ADMIN_EMAILS } from "@/lib/auth/owner";

// CRM-specific additions on top of GLOBAL_ADMIN_EMAILS — mirrors backend
// CRM_EXTRA_ADMIN_EMAILS (admin@balizero.com / admin@zantara.io / asya are
// CRM-domain roles that are not necessarily global admins; damar is
// frontend-only, kept for parity with the pre-existing allowlist).
const CRM_EXTRA_ADMIN_EMAILS: ReadonlySet<string> = new Set([
  "admin@balizero.com",
  "admin@zantara.io",
  "asya@balizero.com",
  "damar@balizero.com",
]);

const CRM_ADMIN_EMAILS: ReadonlySet<string> = new Set([
  ...GLOBAL_ADMIN_EMAILS,
  ...CRM_EXTRA_ADMIN_EMAILS,
]);

export function isCRMAdmin(
  profile: { email?: string; role?: string } | null | undefined,
): boolean {
  if (!profile) return false;
  const email = profile.email?.toLowerCase().trim() ?? "";
  if (CRM_ADMIN_EMAILS.has(email)) return true;
  return profile.role === "admin";
}

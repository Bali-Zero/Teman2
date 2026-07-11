/**
 * Owner + global-admin email SSOT (frontend, UI-gating only).
 *
 * MUST stay in sync with backend `settings.admin_emails_set`
 * (apps/backend-rag/backend/app/core/config.py::_ADMIN_EMAILS_FALLBACK) and
 * `require_owner` (apps/backend-rag/backend/app/deps/owner.py::OWNER_EMAILS).
 *
 * NOTE: `antonellosiano@balizero.com` (not `@gmail.com`) is the correct
 * owner-alias identity — it's the value the backend actually stamps into
 * RBAC checks. `antonellosiano@gmail.com` is a *different* identity used
 * only for personal OAuth / Google Drive (30TB quota owner), never for
 * backend admin/owner gating.
 *
 * Real authorization happens server-side on every gated endpoint, so a
 * misconfigured frontend can never grant access — at worst it hides a
 * control from a real admin/owner.
 */

export const OWNER_EMAILS = new Set(["zero@balizero.com", "antonellosiano@balizero.com"]);

export function isOwner(email: string | null | undefined): boolean {
  return !!email && OWNER_EMAILS.has(email.trim().toLowerCase());
}

/**
 * Global admin allowlist — mirrors backend `admin_emails_set` fallback.
 * Domain-specific admin checks (HR, CRM, ...) should union this with their
 * own extra emails rather than redeclaring the base set.
 */
export const GLOBAL_ADMIN_EMAILS = new Set([
  "zero@balizero.com",
  "asya@balizero.com",
  "antonellosiano@balizero.com",
]);

export function isGlobalAdmin(email: string | null | undefined): boolean {
  return !!email && GLOBAL_ADMIN_EMAILS.has(email.trim().toLowerCase());
}

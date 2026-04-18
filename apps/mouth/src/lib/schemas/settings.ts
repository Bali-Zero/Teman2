/**
 * Settings Zod Schemas
 *
 * Validates responses from the portal/auth settings endpoints:
 *   - GET  /api/auth/profile                       (UserProfile)
 *   - GET  /api/portal/settings                    (client_preferences envelope)
 *   - GET  /api/portal/notifications/prefs         (email + whatsapp channel prefs)
 *   - PUT  /api/portal/notifications/prefs         (same shape in/out)
 *
 * Backend sources of truth (verified 2026-04-18):
 *   - /api/auth/profile → `apps/backend-rag/backend/app/routers/auth.py:435`
 *     Returns `UserProfile` defined in `backend/app/models/__init__.py:122`.
 *     Pydantic model has id/user_id aliases, `language` with default "en",
 *     optional tone/complexity/timezone/role_level/status/avatar/metadata.
 *   - /api/portal/settings → `apps/backend-rag/backend/app/routers/portal.py:669`
 *     Returns `{ success, data: { email_notifications, whatsapp_notifications,
 *     language, timezone } }` from
 *     `backend/services/portal/_mixins/messaging.py:160 (get_preferences)`.
 *   - /api/portal/notifications/prefs →
 *     `apps/backend-rag/backend/app/routers/portal_notification_prefs.py`
 *     GET returns `NotificationPrefsOut` = `{ email_enabled, wa_enabled,
 *     wa_phone: str | None }`. PUT accepts `NotificationPrefsIn` with same
 *     fields (wa_phone validated against E.164 without the leading '+').
 *     When migration 110 is missing, PUT raises HTTP 503 with
 *     `{ "detail": "notification_prefs unavailable — run migration 110" }`.
 *     GET silently falls back to `_default_prefs()` on read failure (no 503).
 *
 * IMPORTANT: `UserProfile` includes many legacy/compat fields (id+user_id,
 * language+language_preference, metadata+meta_json) because the Pydantic
 * model normalises both sides. We model both but mark the alias fields as
 * optional so either is valid.
 */

import { z } from "zod";

// ============================================
// LANGUAGE ENUM
// ============================================

/**
 * Supported UI languages.
 *
 * The BE does NOT enforce a strict enum on `language` (it's a plain str in
 * Python), but the portal only ships it/en/id translations. We keep this
 * as a union of known values plus a loose `.or(z.string())` fallback at
 * consumption sites for forward-compat when we schema-validate the BE
 * profile response.
 */
export const Language = z.enum(["it", "en", "id"]);
export type Language = z.infer<typeof Language>;

// ============================================
// USER PROFILE — /api/auth/profile
// ============================================

/**
 * Matches `UserProfile` at `backend/app/models/__init__.py:122`.
 *
 * The Pydantic model accepts either `id` or `user_id` (with a
 * model_validator that promotes whichever is provided). After
 * `model_post_init`, both are present on the returned object. We therefore
 * require at least one to be a non-empty string via `.refine`.
 *
 * - `language` has a Pydantic default of "en" → always present in the
 *   response. We model it as `z.string()` (not the Language enum) because
 *   the DB may contain legacy rows with non-IETF values; consumers should
 *   narrow with `Language.safeParse(profile.language)` when they need it.
 * - `metadata` and `meta_json` are synced by `model_post_init` (see the
 *   Pydantic file) so both are typically echoed. Both are optional for
 *   forward-compat.
 */
export const UserProfile = z
  .object({
    id: z.string().nullable().optional(),
    user_id: z.string().nullable().optional(),

    email: z.string(),
    name: z.string(),
    role: z.string(),
    status: z.string().nullable().optional(),
    avatar: z.string().nullable().optional(),

    // Language: BE default is "en", but not enforced as enum server-side.
    language: z.string(),
    language_preference: z.string().nullable().optional(),

    // Oracle-specific preferences (all optional on the BE side).
    tone: z.string().nullable().optional(),
    complexity: z.string().nullable().optional(),
    timezone: z.string().nullable().optional(),
    role_level: z.string().nullable().optional(),

    // Metadata: BE syncs `metadata` and `meta_json` aliases.
    metadata: z.record(z.string(), z.unknown()).nullable().optional(),
    meta_json: z.record(z.string(), z.unknown()).optional(),
  })
  .refine(
    (v) =>
      (typeof v.id === "string" && v.id.length > 0) ||
      (typeof v.user_id === "string" && v.user_id.length > 0),
    { message: "Either 'id' or 'user_id' must be provided" },
  );
export type UserProfile = z.infer<typeof UserProfile>;

// ============================================
// PORTAL SETTINGS — /api/portal/settings
// ============================================

/**
 * Inner `data` of `GET /api/portal/settings`.
 *
 * Mirrors `PortalMessagingMixin.get_preferences` dict (messaging.py:187).
 * The BE defaults are `{ email_notifications: true, whatsapp_notifications:
 * true, language: "en", timezone: "Asia/Jakarta" }` when the client row is
 * missing.
 */
export const PortalSettings = z.object({
  email_notifications: z.boolean(),
  whatsapp_notifications: z.boolean(),
  language: z.string(),
  timezone: z.string(),
});
export type PortalSettings = z.infer<typeof PortalSettings>;

/**
 * Envelope emitted by `portal.get_preferences` router:
 *   `{ "success": true, "data": <PortalSettings> }`.
 */
export const PortalSettingsResponse = z.object({
  success: z.boolean(),
  data: PortalSettings,
});
export type PortalSettingsResponse = z.infer<typeof PortalSettingsResponse>;

// ============================================
// NOTIFICATION PREFS — /api/portal/notifications/prefs
// ============================================

/**
 * Channels currently supported by `portal_notification_prefs.py`.
 *
 * Only `email` and `wa` (WhatsApp) are persisted in the
 * `notification_prefs` table (migration 110). Telegram / SMS are out of
 * scope for portal clients; the Task 7 watchdog uses email+WA only.
 */
export const NotificationChannel = z.enum(["email", "wa"]);
export type NotificationChannel = z.infer<typeof NotificationChannel>;

/**
 * Notification event families the portal user cares about. These are
 * implicit in the BE model (one `email_enabled` + one `wa_enabled` toggle
 * covers all deadline/practice events today), but we expose the enum here
 * so future UI can offer per-event toggles without a schema churn.
 */
export const NotificationEvent = z.enum([
  "deadline_reminder",
  "practice_update",
  "document_request",
]);
export type NotificationEvent = z.infer<typeof NotificationEvent>;

/**
 * Matches `NotificationPrefsOut` at
 * `backend/app/routers/portal_notification_prefs.py:49`.
 *
 * - `email_enabled`: required boolean.
 * - `wa_enabled`: required boolean.
 * - `wa_phone`: E.164 digits WITHOUT the leading '+' (see `_E164_RE` in
 *   the router). May be `null` when unset — we accept null or a string
 *   and do NOT regex-validate here (the BE owns the canonical validation
 *   on PUT).
 */
export const NotificationPrefs = z.object({
  email_enabled: z.boolean(),
  wa_enabled: z.boolean(),
  wa_phone: z.string().nullable(),
});
export type NotificationPrefs = z.infer<typeof NotificationPrefs>;

/**
 * Payload accepted by `PUT /api/portal/notifications/prefs`. Matches
 * `NotificationPrefsIn`: all fields have defaults server-side so they
 * are optional on the wire, but we keep them required on our client to
 * force callers to declare intent explicitly.
 *
 * The BE returns HTTP 422 if `wa_enabled=true` but `wa_phone` is missing
 * or non-E.164. We model `wa_phone` with a refine for early client-side
 * feedback (keeps the PUT shape below in sync with the router validator).
 */
const E164_NO_PLUS = /^[1-9]\d{6,14}$/;
export const NotificationPrefsInput = z
  .object({
    email_enabled: z.boolean(),
    wa_enabled: z.boolean(),
    wa_phone: z.string().nullable().optional(),
  })
  .superRefine((v, ctx) => {
    if (v.wa_phone != null && v.wa_phone !== "") {
      if (!E164_NO_PLUS.test(v.wa_phone)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["wa_phone"],
          message: "wa_phone must be E.164 digits only (no +)",
        });
      }
    }
    if (v.wa_enabled && (v.wa_phone == null || v.wa_phone === "")) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["wa_phone"],
        message: "wa_phone is required when wa_enabled is true",
      });
    }
  });
export type NotificationPrefsInput = z.infer<typeof NotificationPrefsInput>;

// ============================================
// MIGRATION-MISSING ERROR (503)
// ============================================

/**
 * FastAPI 503 body raised by PUT when the `notification_prefs` table
 * is missing (migration 110 not yet applied):
 *   `{ "detail": "notification_prefs unavailable — run migration 110" }`.
 *
 * Exposed as a schema so hooks can distinguish "migration missing"
 * (graceful degradation, keep UI alive) from genuine 5xx errors.
 */
export const MigrationMissingError = z.object({
  detail: z.string(),
});
export type MigrationMissingError = z.infer<typeof MigrationMissingError>;

/**
 * Heuristic check — the BE message contains the literal "migration 110".
 * We also treat any HTTP 503 from the prefs PUT as "migration missing" in
 * the hook layer, since there is no other reason the router raises 503.
 */
export function isMigrationMissingMessage(msg: string | undefined): boolean {
  if (!msg) return false;
  return (
    /migration\s+110/i.test(msg) || /notification_prefs unavailable/i.test(msg)
  );
}

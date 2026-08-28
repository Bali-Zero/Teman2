/**
 * Shared shape for the three files that make up the magic-link redemption
 * flow (`route.ts` GET landing, `continue/page.tsx` form,
 * `exchange/route.ts` POST). Kept in one module because the previous version
 * duplicated these constants across two files verbatim, which is a drift the
 * next edit pays for.
 *
 * The patterns MIRROR the backend and are not a security boundary — the
 * backend at `apps/backend-rag/backend/app/routers/garuda_portal_auth.py:225,234`
 * is. Validating here is what lets a mangled link say "ask for a new one"
 * instead of a round trip.
 */

/** `MagicLinkRequest.result_id` — `garuda_portal_auth.py:225`. */
export const RESULT_ID_PATTERN = /^[A-Za-z0-9_-]{22,128}$/;

/** `MagicLinkExchange.token` — `garuda_portal_auth.py:234`. */
export const TOKEN_MIN_LENGTH = 32;
export const TOKEN_MAX_LENGTH = 2048;

/**
 * Carries the token from the emailed URL to the form POST without it ever
 * appearing in a rendered document. HttpOnly and scoped to this subtree.
 */
export const PENDING_COOKIE = "garuda_magic_pending";

/** Only has to survive one redirect and one button press. */
export const PENDING_COOKIE_MAX_AGE_SECONDS = 600;

/**
 * Deliberately NOT `/`: the credential must not ride along on every other
 * request the browser makes to balizero.com.
 */
export const PENDING_COOKIE_PATH = "/visa/voa/auth";

/** The account cookie the backend mints; this flow forwards it verbatim. */
export const ACCOUNT_COOKIE_PREFIX = "garuda_session=";

/** Every failure funnels here — uniform, because the backend answers ONE
 * non-enumerating error for invalid / expired / already-consumed tokens
 * (DECISIONS.md Q1) and this flow must not re-introduce the distinction. */
export const FAILURE_LOCATION = "/visa/voa/auth/continue?error=invalid";

export function isLoopback(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

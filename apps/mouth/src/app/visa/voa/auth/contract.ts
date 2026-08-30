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
 * Carries BOTH halves of the emailed link -- the token and the result id it
 * was issued for -- from the landing GET to the form POST, without either
 * ever appearing in a rendered document. HttpOnly and scoped to this subtree.
 *
 * The two travel TOGETHER, in one cookie, on purpose. An earlier version took
 * the token from here and the result id from a hidden form field; nothing
 * bound them, so a second tab opening link B overwrote the shared cookie and
 * submitting tab A redeemed token B while redirecting to A's upload page --
 * a session for one application landing on another application's URL. A
 * forged hidden field did the same thing deliberately. Found by the
 * cross-family council (Codex sol, 2026-08-28), which is also why the form
 * now carries no fields at all: one cookie, written once, read once.
 */
export const PENDING_COOKIE = "garuda_magic_pending";

/**
 * `.` cannot occur in a result id (`RESULT_ID_PATTERN` admits only
 * `[A-Za-z0-9_-]`), so the FIRST `.` is unambiguously the boundary no matter
 * what the opaque token contains.
 */
const PENDING_SEPARATOR = ".";

export function encodePending(resultId: string, token: string): string {
  return `${resultId}${PENDING_SEPARATOR}${token}`;
}

/**
 * Returns the pair only if BOTH halves are well-formed. Anything else -- no
 * cookie, no separator, a bad result id, a token of the wrong length -- is a
 * single `null`, because every caller funnels all of those to the same
 * non-enumerating failure.
 */
export function decodePending(
  raw: string | undefined,
): { resultId: string; token: string } | null {
  if (typeof raw !== "string") return null;
  const cut = raw.indexOf(PENDING_SEPARATOR);
  if (cut <= 0) return null;
  const resultId = raw.slice(0, cut);
  const token = raw.slice(cut + 1);
  if (!RESULT_ID_PATTERN.test(resultId)) return null;
  if (token.length < TOKEN_MIN_LENGTH || token.length > TOKEN_MAX_LENGTH) {
    return null;
  }
  return { resultId, token };
}

/** Only has to survive one redirect and one button press. */
export const PENDING_COOKIE_MAX_AGE_SECONDS = 600;

/**
 * Deliberately NOT `/`: the credential must not ride along on every other
 * request the browser makes to balizero.com.
 */
export const PENDING_COOKIE_PATH = "/visa/voa/auth";

/** The account cookie the backend mints; this flow forwards it verbatim. */
export const ACCOUNT_COOKIE_PREFIX = "garuda_session=";

/**
 * True only if one of the forwarded `Set-Cookie` lines is an account session
 * with a NON-EMPTY value.
 *
 * The name alone is not enough: `garuda_session=; Max-Age=0` is how a cookie
 * gets DELETED, and it starts with the same prefix. Both council seats
 * (Codex sol and Kimi K3, independently, 2026-08-28) pointed at the earlier
 * `startsWith` check for exactly this -- it would have read a deletion as a
 * successful sign-in and sent an anonymous visitor to the upload page.
 */
export function hasAccountSession(setCookies: string[]): boolean {
  // THE LAST matching header decides, not "some header looks right". RFC 6265
  // processes `Set-Cookie` in order and a later one for the same name replaces
  // the earlier, so `[garuda_session=real, garuda_session=; Max-Age=0]` leaves
  // the browser with NO session — and `.some()` would have called that a
  // successful sign-in. Adversarial review 2026-08-28; this is the property
  // that actually matters (what the jar holds afterwards), which the three
  // earlier versions of this check — presence, then name, then name+value —
  // each only approximated.
  let last: string | null = null;
  for (const c of setCookies) {
    if (c.startsWith(ACCOUNT_COOKIE_PREFIX)) {
      last = c.slice(ACCOUNT_COOKIE_PREFIX.length).split(";", 1)[0];
    }
  }
  if (last === null) return false;
  // RFC 6265 permits a DQUOTE-wrapped value, so `garuda_session=""` is an
  // EMPTY session that a bare length check would pass.
  return last.trim().replace(/^"|"$/g, "").length > 0;
}

/** Every failure funnels here — uniform, because the backend answers ONE
 * non-enumerating error for invalid / expired / already-consumed tokens
 * (DECISIONS.md Q1) and this flow must not re-introduce the distinction. */
export const FAILURE_LOCATION = "/visa/voa/auth/continue?error=invalid";

/**
 * Mirrors the backend's `_LOOPBACK_HOSTS`
 * (`garuda_portal_auth.py:238` — `{"localhost", "127.0.0.1", "::1"}`). The
 * IPv6 entry was missing here, which fails CLOSED (a `Secure` cookie the
 * `http://[::1]` dev server cannot store) rather than open, but it broke
 * local dev over IPv6 and this file claims to mirror the backend.
 * ONLY the `localhost` entry is reachable through this path. MEASURED
 * 2026-08-29: `new NextRequest("http://127.0.0.1:3000/x")` yields
 * `new URL(request.url).hostname === "localhost"`, and the same holds for
 * `http://[::1]:3000` — a plain `new URL(...)` does NOT normalise (it keeps
 * `127.0.0.1` / the bracketed `[::1]`), which is what made the other entries
 * look testable. Confirmed by mutation on the same date, and stated as a
 * DIRECTION rather than a count so nothing here can go stale unnoticed:
 * deleting `"localhost"` turns this `route.test.ts` case RED —
 * `omits Secure on localhost so local dev can accept the cookie`
 * (kept on one line so it stays greppable) — while deleting `"127.0.0.1"`
 * leaves every test in that file GREEN. Re-derive it, do not trust this
 * sentence: delete an entry, run
 * `npx vitest run src/app/visa/voa/auth/route.test.ts` from `apps/mouth`.
 * (An earlier revision of this comment carried a literal red-count that was
 * already wrong one commit later — it had been measured against a two-row
 * `it.each` that the same PR collapsed into the single named test above.)
 * The three non-`localhost` entries are kept as defensive parity with the
 * backend list and deliberately carry NO test, because a test written
 * against them passes whether or not they are present — which is worse than
 * no test.
 */
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

export function isLoopback(hostname: string): boolean {
  return LOOPBACK_HOSTS.has(hostname.toLowerCase());
}

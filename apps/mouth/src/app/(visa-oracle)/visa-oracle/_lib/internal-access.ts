/**
 * SERVER-ONLY. Internal PIN access for the Visa Oracle full-power preview.
 *
 * Never import this from a client component: it reads the PIN from the
 * server-side environment and uses `node:crypto`.
 *
 * WHAT THIS IS: a soft internal gate so the Bali Zero team can exercise the
 * real engine while `VISA_ENGINE_EVALUATE_MODE` is still SHADOW. It is NOT
 * authentication and NOT a security boundary — its strength is exactly the
 * entropy of `VISA_ORACLE_INTERNAL_PIN` (a 4-digit PIN is brute-forceable in
 * seconds by a determined actor). It keeps casual passers-by out of an
 * unfinished surface; it must never be relied on to protect anything whose
 * disclosure would actually harm.
 *
 * WHY A SIGNED COOKIE, not a bare flag: `HttpOnly` stops client JS from
 * READING a cookie, it does not stop a person from WRITING one in devtools.
 * A bare `vo_internal=1` would therefore be trivially forgeable by anyone who
 * guessed the cookie's name. The value is an HMAC over the expiry, keyed by a
 * value derived from the PIN, so forging it costs the same as guessing the
 * PIN — never less.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

export const INTERNAL_ACCESS_COOKIE = "vo_internal";

/** 30 days: long enough that the team unlocks once, short enough to lapse. */
export const INTERNAL_ACCESS_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

const KEY_LABEL = "vo-internal-cookie-key-v1";
const TOKEN_LABEL = "vo-internal";

/**
 * The configured PIN, or `null` when unset. Unset means the gate is CLOSED:
 * no unlock can succeed and no cookie can verify (fail-closed, so a missing
 * env var can never silently open the internal surface to the public).
 */
export function configuredPin(): string | null {
  const raw = process.env.VISA_ORACLE_INTERNAL_PIN;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function signingKey(pin: string): Buffer {
  return createHmac("sha256", pin).update(KEY_LABEL).digest();
}

function signature(pin: string, expiresAtMs: number): string {
  return createHmac("sha256", signingKey(pin))
    .update(`${TOKEN_LABEL}|${expiresAtMs}`)
    .digest("base64url");
}

/** Constant-time string compare that never throws on length mismatch. */
export function safeEquals(a: string, b: string): boolean {
  const left = Buffer.from(a, "utf8");
  const right = Buffer.from(b, "utf8");
  if (left.length !== right.length) return false;
  try {
    return timingSafeEqual(left, right);
  } catch {
    return false;
  }
}

/** Mint a cookie value that proves PIN possession until `expiresAtMs`. */
export function mintInternalAccessToken(
  pin: string,
  expiresAtMs: number,
): string {
  return `${expiresAtMs}.${signature(pin, expiresAtMs)}`;
}

/**
 * True iff `token` is a well-formed, unexpired, correctly-signed cookie value
 * for the currently configured PIN. Rotating the PIN invalidates every
 * outstanding token, which is what makes "togliamo il pin" a real revocation.
 */
export function verifyInternalAccessToken(
  token: string | undefined,
  nowMs: number = Date.now(),
): boolean {
  const pin = configuredPin();
  if (pin === null || !token) return false;

  const separator = token.indexOf(".");
  if (separator <= 0) return false;

  const expiresAtRaw = token.slice(0, separator);
  const presented = token.slice(separator + 1);
  if (!/^\d{1,15}$/.test(expiresAtRaw) || presented.length === 0) return false;

  const expiresAtMs = Number(expiresAtRaw);
  if (!Number.isSafeInteger(expiresAtMs) || expiresAtMs <= nowMs) return false;

  return safeEquals(presented, signature(pin, expiresAtMs));
}

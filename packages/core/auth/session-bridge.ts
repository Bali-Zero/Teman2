export const BZ_SESSION_COOKIE = "bz_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30; // 30 days

function uuidV4(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID)
    return crypto.randomUUID();
  // Fallback for environments without crypto.randomUUID
  const b = new Uint8Array(16);
  const g = (globalThis.crypto as Crypto | undefined) ?? undefined;
  if (!g) throw new Error("crypto unavailable");
  g.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (n) => n.toString(16).padStart(2, "0"));
  return `${h.slice(0, 4).join("")}-${h.slice(4, 6).join("")}-${h.slice(6, 8).join("")}-${h.slice(8, 10).join("")}-${h.slice(10, 16).join("")}`;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) return trimmed.slice(prefix.length);
  }
  return null;
}

function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  const isSecure =
    typeof location !== "undefined" && location.protocol === "https:";
  const parts = [
    `${name}=${value}`,
    "path=/",
    "SameSite=Lax",
    `Max-Age=${MAX_AGE_SECONDS}`,
  ];
  if (
    typeof location !== "undefined" &&
    location.hostname.endsWith("balizero.com")
  ) {
    parts.push("Domain=.balizero.com");
  }
  if (isSecure) parts.push("Secure");
  document.cookie = parts.join("; ");
}

export function getOrCreateSessionId(): string {
  const existing = readCookie(BZ_SESSION_COOKIE);
  if (existing) return existing;
  const fresh = uuidV4();
  writeCookie(BZ_SESSION_COOKIE, fresh);
  return fresh;
}

// Same 5 UTM params the outbound builders (whatsapp-utm.ts, social-utm.ts)
// stamp on every CTA — mirrored here for the inbound read so attribution
// uses one shared vocabulary in both directions.
const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;

/**
 * Reads inbound `utm_*` + referring hostname from the CURRENT navigation —
 * but ONLY on a session's genuine first touch (no `bz_session` cookie yet).
 * Must be called BEFORE `getOrCreateSessionId()` mints that cookie, or every
 * call would read as "first touch". Returns `undefined` (never an empty
 * object) when there's nothing to capture or this is a return visit, so a
 * caller can omit the key entirely rather than clobbering an already-
 * persisted first touch with an empty overwrite (funnel_sessions.step_state
 * merges by top-level key, not deep-merge — see funnel.py `||` comment).
 *
 * Only the referring HOSTNAME is kept, never the full referrer URL — a
 * referrer's path/query can carry a search term or an internal identifier
 * that isn't ours to log (Law 2 minimization), and "which site sent them"
 * is all attribution needs.
 */
export function readFirstTouchAttribution():
  Record<string, string> | undefined {
  if (readCookie(BZ_SESSION_COOKIE)) return undefined;
  if (typeof window === "undefined") return undefined;

  const attribution: Record<string, string> = {};
  const params = new URLSearchParams(window.location.search);
  for (const key of UTM_KEYS) {
    const value = params.get(key);
    if (value) attribution[key] = value;
  }

  try {
    const referrer = typeof document !== "undefined" ? document.referrer : "";
    if (referrer) {
      const referrerHost = new URL(referrer).hostname;
      if (referrerHost && referrerHost !== window.location.hostname) {
        attribution.referrer_host = referrerHost;
      }
    }
  } catch {
    /* malformed/opaque referrer — skip, never throw on attribution */
  }

  return Object.keys(attribution).length > 0 ? attribution : undefined;
}

export async function attachToServerSession(payload: {
  funnel: "visa" | "kbli" | "tax" | "property" | "home";
  step_state?: Record<string, unknown>;
}): Promise<void> {
  const firstTouch = readFirstTouchAttribution();
  const sessionId = getOrCreateSessionId();
  const step_state = firstTouch
    ? { ...payload.step_state, first_touch: firstTouch }
    : payload.step_state;
  await fetch("/api/funnel/session/touch", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      funnel: payload.funnel,
      step_state,
    }),
  });
}

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

export async function attachToServerSession(payload: {
  funnel: "visa" | "kbli" | "tax" | "property" | "home";
  step_state?: Record<string, unknown>;
}): Promise<void> {
  const sessionId = getOrCreateSessionId();
  await fetch("/api/funnel/session/touch", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, ...payload }),
  });
}

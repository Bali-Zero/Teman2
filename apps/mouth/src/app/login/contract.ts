import { ApiError } from "@/lib/api/error-handler";

/**
 * The two decisions /login makes that are not presentation, kept OUT of
 * page.tsx on purpose: a Next.js page module may export only the framework's
 * own symbols, and `tsc` fails TS2344 against .next/dev/types on any other
 * named export. They are also the two things worth testing directly.
 */

/** The five states this page can honestly be in. */
export type LoginStage =
  "idle" | "authenticating" | "success" | "denied" | "unreachable";

/** Hosts a signed-in staff member may legitimately be sent back to. */
const FIRST_PARTY_SUFFIX = ".balizero.com";
const FIRST_PARTY_APEX = "balizero.com";

/**
 * Accept a redirect target only when it stays inside Bali Zero.
 *
 * Two shapes reach this page and both are legitimate:
 *   - a PATH, from the prime mode switcher (`/login?redirect=/prime`);
 *   - an ABSOLUTE URL, from the workspace layout, which sends
 *     `?redirect=${encodeURIComponent(window.location.href)}`, and from the SSO
 *     subdomains (mail/calendar/drive/knowledge.balizero.com) that bounce their
 *     unauthenticated visitors here. Refusing those would drop a staff member on
 *     /dashboard instead of the page they asked for.
 *
 * Refused, each for a reason a reviewer can check: any scheme that is not
 * https (so `javascript:` and `data:` cannot arrive), any host that is not
 * balizero.com or one of its subdomains, the protocol-relative `//evil.test`
 * (which a browser resolves as absolute), and the backslash form `/\evil.test`
 * (which some browsers normalise into it). `new URL()` does the host parsing,
 * so the userinfo trick `https://balizero.com@evil.test` is read as evil.test
 * and refused, which is the whole reason not to do this with a regex.
 */
export function firstPartyRedirect(raw: string | null): string | null {
  if (!raw) return null;

  if (raw.startsWith("/")) {
    if (raw.startsWith("//")) return null;
    if (raw.startsWith("/\\")) return null;
    return raw;
  }

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "https:") return null;
  const host = url.hostname.toLowerCase();
  if (host !== FIRST_PARTY_APEX && !host.endsWith(FIRST_PARTY_SUFFIX)) {
    return null;
  }
  return url.href;
}

/**
 * Which plate an error deserves.
 *
 * The old page had one failure state and called it "denied", so a 500 told a
 * staff member their PIN was wrong and sent them to reset a password that was
 * never the problem. The split is by STATUS, not by a substring of the message:
 *
 *   4xx  -> the request. Wrong credentials (401/403), but also a PIN that is
 *           not 4-8 digits (the backend answers 400) or an address pydantic
 *           rejects (422). All of those are "look at what you typed".
 *   408, 429, 5xx, and anything thrown by fetch -> the service.
 */
export function stageForError(error: unknown): "denied" | "unreachable" {
  if (error instanceof ApiError) {
    const status = error.statusCode;
    if (status === 408 || status === 429) return "unreachable";
    if (status >= 400 && status < 500) return "denied";
    return "unreachable";
  }
  // A TypeError thrown by fetch is a network failure, not a bad PIN.
  return "unreachable";
}

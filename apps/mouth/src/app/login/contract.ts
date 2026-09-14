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
const FIRST_PARTY_APEX = "balizero.com";
const FIRST_PARTY_SUFFIX = ".balizero.com";

/**
 * Where a just-authenticated staff member may be sent.
 *
 * Written to a spec (windows/K1d-REDIRECT-SPEC.md, amended 15:55) after three
 * attempts of mine carried the same hole. The rule that closes it is one
 * sentence: RESOLVE EVERY CANDIDATE FIRST, THEN JUDGE THE PARSED URL.
 *
 * String-matching cannot work here, and the reason is worth keeping. Browsers
 * strip TAB, LF and CR before they parse a URL, and `URLSearchParams.get()`
 * percent-decodes — so `?redirect=/%09/evil.test` arrives as `/`, TAB, `/`,
 * `evil.test`: it begins with a single `/`, carries no leading `//`, and passes
 * any prefix test that can be written. The browser then drops the TAB and
 * resolves it as `//evil.test`, which is `https://evil.test/`. `/%0A/` and
 * `/%0D/` do the same, and so do `/\evil.test` and `\\evil.test`. Resolution
 * sees all five for what they are, because it asks the same parser the browser
 * will use.
 *
 * Two destinations are legitimate and both are kept:
 *
 *   - THIS origin. A path from the prime mode switcher, or an absolute URL
 *     from (workspace)/layout.tsx, which sends
 *     `?redirect=${window.location.href}`. The RESOLVED path is returned, not
 *     the string and not an absolute href, so the browser does not take a full
 *     reload through its own hostname.
 *   - A first-party SIBLING over https. apps/admin-dashboard/middleware.ts
 *     bounces to `kita.balizero.com/login?redirect=https://admin.balizero.com/…`,
 *     and proxy.ts records the same for mail/calendar/drive/knowledge. Those
 *     staff must land back where they were, so the sibling's `href` is
 *     returned. http is refused for a sibling: only our own origin may be
 *     plain http, and only because a dev server is.
 */
export function firstPartyRedirect(
  raw: string | null,
  origin: string,
): string | null {
  if (!raw) return null;

  let u: URL;
  try {
    // A bare path resolves against OUR origin, which is what turns
    // `/<TAB>/evil.test`, `//evil.test` and `/\evil.test` into evil.test here
    // rather than at `location.replace()` time.
    u = new URL(raw, origin);
  } catch {
    return null;
  }

  // https everywhere, except our own origin — a dev server is literally http.
  if (u.protocol !== "https:" && u.origin !== origin) return null;

  if (u.origin === origin) {
    if (u.pathname.startsWith("/login")) return null; // no loop back into the gate
    return u.pathname + u.search + u.hash;
  }

  const host = u.hostname.toLowerCase();
  if (host !== FIRST_PARTY_APEX && !host.endsWith(FIRST_PARTY_SUFFIX)) {
    return null;
  }
  return u.href;
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

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

/**
 * Where a just-authenticated staff member may be sent.
 *
 * Written to a spec (windows/K1d-REDIRECT-SPEC.md) after three attempts of
 * mine carried the same hole. The rule that closes it is one sentence: JUDGE
 * THE RESOLVED URL, NEVER THE STRING.
 *
 * String-matching cannot work here, and the reason is worth keeping. Browsers
 * strip TAB, LF and CR before they parse a URL, and `URLSearchParams.get()`
 * percent-decodes — so `?redirect=/%09/evil.test` arrives as the seven
 * characters `/`, TAB, `/`, `e`… , begins with a single `/`, contains no `//`
 * at the front, and passes any prefix test you can write. The browser then
 * drops the TAB and resolves it as `//evil.test`, which is `https://evil.test/`.
 * `/%0A/` and `/%0D/` do the same. Resolution sees all three for what they are.
 *
 * What is accepted: anything that resolves to THIS origin over http or https
 * and is not the login page itself. That covers both shapes that really
 * arrive — a path from the prime mode switcher, and an absolute same-origin
 * URL from (workspace)/layout.tsx and the SSO subdomains, whose PATH is
 * returned rather than its string.
 */
export function safeRedirect(
  raw: string | null,
  origin: string,
  fallback = "/dashboard",
): string {
  if (!raw) return fallback;
  let u: URL;
  try {
    u = new URL(raw, origin);
  } catch {
    return fallback;
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") return fallback;
  // Same origin only. This one line covers //host, /\host, /%09/host, the
  // userinfo trick and every look-alike hostname, because the browser's own
  // parser has already decided what the target really is.
  if (u.origin !== origin) return fallback;
  // No loop back into the gate.
  if (u.pathname.startsWith("/login")) return fallback;
  return u.pathname + u.search + u.hash;
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

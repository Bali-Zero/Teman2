/**
 * GARUDA VOA — which language the funnel speaks, as ONE variable.
 *
 * Two owner statements collide here, and this file resolves the collision the
 * same way PR #6932 resolved red-vs-copper: build on a token, ship the value
 * currently ruled, and give the owner a live preview of the other one.
 *
 *   - product.yaml decision 5, binding copy constraint 5a (ratified
 *     2026-08-25): "The public funnel is ENGLISH. All of it."
 *   - GARUDA-VOA mandate 2026-09-19, accent (6): "EN/ID parity".
 *
 * `VOA_LOCALE_RULING` is that variable. Shipped as `english-by-default`, so a
 * visitor who never asks — including one whose site preference is Bahasa —
 * is served English exactly as 5a requires. Indonesian is reachable only by
 * TYPING `?lang=id`, which is the site's own convention for asking for a
 * language (`src/i18n/lang-query-param.test.tsx`), and is here a preview
 * channel for the owner's decision, not a switcher the funnel offers.
 *
 * The day the owner rules EN/ID parity live, the flip is this constant to
 * `follow-site-preference`: the stored `blog-language` preference then decides,
 * and nothing else in the funnel changes. `voa-i18n.parity.guard.test.tsx`
 * pins both readings of the resolver, so neither is a coincidence.
 */

export type VoaLocale = "en" | "id";

export type VoaLocaleRuling =
  /** 5a in force: only an explicit `?lang=id` shows Indonesian. */
  | "english-by-default"
  /** EN/ID parity ruled live: the site preference decides, `?lang` overrides. */
  | "follow-site-preference";

/** The ruling in force. One line to flip, and it is the ONLY line. */
export const VOA_LOCALE_RULING: VoaLocaleRuling = "english-by-default";

export const VOA_LOCALE_QUERY_PARAM = "lang";

/**
 * The key `I18nProvider` writes (src/i18n/index.tsx) — read, never written,
 * so the funnel cannot change a preference it merely honours.
 */
export const SITE_LOCALE_PREFERENCE_KEY = "blog-language";

/**
 * Where the preview language lives for the rest of the journey.
 *
 * `?lang=id` is typed ONCE, on the first screen. The wizard then navigates to
 * the verdict with `router.push`, which does not carry a query string, so
 * without this the funnel answered in Indonesian would return its verdict in
 * English — the half-translated journey this lane refuses to ship.
 *
 * `sessionStorage`, not `localStorage`, and deliberately: the preview belongs
 * to the tab that asked for it. Closing the tab ends it, and nothing about a
 * customer's language survives into a later visit, where constraint 5a would
 * again decide alone.
 */
export const VOA_LOCALE_SESSION_KEY = "bz.garuda_voa.preview-locale";

/**
 * THE SAME CHOICE, IN A COOKIE, BECAUSE THE JOURNEY LEAVES THE TAB.
 *
 * `VOA_LOCALE_SESSION_KEY` carries the language across `router.push` inside
 * one tab, which is the whole funnel up to the verdict. The paid half is not
 * in that tab: the magic link arrives by EMAIL and opens a NEW one, where
 * sessionStorage is empty and the URL carries no `?lang=`. Without this
 * cookie, a visitor who answered in Bahasa reads the upload, checkout and
 * order screens in English — and `auth/continue` is a SERVER component, so it
 * cannot read browser storage at all, only a cookie.
 *
 * SCOPED TO THE JOURNEY, NOT TO THE PERSON. `Max-Age` is one hour because the
 * magic link itself expires in fifteen minutes: this covers the hop it exists
 * for and nothing beyond it. That matters — constraint 5a says a visitor who
 * does not ask reads English, and a durable preference would quietly overrule
 * it on every later visit. An hour is a journey; a year would be a ruling.
 *
 * `SameSite=Lax` so the cookie survives the top-level navigation FROM the
 * mail client, which is exactly the hop being fixed. No `Secure` flag is set
 * here because the value is a two-letter language code, not a credential, and
 * the attribute would make it undebuggable on http://localhost.
 */
export const VOA_LOCALE_COOKIE = "bz_voa_lang";
export const VOA_LOCALE_COOKIE_MAX_AGE_S = 60 * 60;

function asVoaLocale(raw: string | null | undefined): VoaLocale | null {
  if (raw === "id" || raw === "en") return raw;
  return null;
}

/**
 * Pure, so the ruling is testable without a browser: `requested` is the
 * `?lang=` value, `preference` the stored site language. Anything unknown
 * ("de", "", null) falls back to English rather than throwing — an unreadable
 * language code is not a reason to show a customer a broken screen.
 */
export function resolveVoaLocale({
  requested,
  session,
  journey,
  preference,
  ruling = VOA_LOCALE_RULING,
}: {
  requested?: string | null;
  /** What `?lang=` set earlier in THIS tab's journey. */
  session?: string | null;
  /** What `?lang=` set earlier in this BROWSER, within the last hour. */
  journey?: string | null;
  preference?: string | null;
  ruling?: VoaLocaleRuling;
}): VoaLocale {
  const asked = asVoaLocale(requested);
  if (asked) return asked;
  const carried = asVoaLocale(session);
  if (carried) return carried;
  // The tab is gone but the journey is not: the mail client opened a new one.
  const hopped = asVoaLocale(journey);
  if (hopped) return hopped;
  if (ruling === "follow-site-preference") {
    return asVoaLocale(preference) ?? "en";
  }
  return "en";
}

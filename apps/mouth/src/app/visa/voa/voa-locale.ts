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
  preference,
  ruling = VOA_LOCALE_RULING,
}: {
  requested?: string | null;
  preference?: string | null;
  ruling?: VoaLocaleRuling;
}): VoaLocale {
  const asked = asVoaLocale(requested);
  if (asked) return asked;
  if (ruling === "follow-site-preference") {
    return asVoaLocale(preference) ?? "en";
  }
  return "en";
}

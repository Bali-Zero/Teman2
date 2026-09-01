// Named `*Messages` — NOT `it`/`id` — because vitest's global `it()` test
// function lives in this module's scope too; a default import literally named
// `it` shadows it and every `it(...)` below silently resolves to the JSON.
import enMessages from "./locales/en.json";
import itMessages from "./locales/it.json";
import idMessages from "./locales/id.json";
import frMessages from "./locales/fr.json";
import ruMessages from "./locales/ru.json";
import { LOCALES, type Locale } from "./types";

/**
 * Locale key-set parity — a RATCHET, not a wall.
 *
 * There was no parity check of any kind in this directory until 2026-08-31,
 * and the absence is what the 2026-07-29 owner decision was reacting to:
 * `ru`/`fr` were withdrawn from `OFFERED_LOCALES` because "their translations
 * are complete but drift against the English source until the translator
 * re-runs" (`types.ts`). Drift with no instrument is drift nobody can see
 * shrink — the locales stay withdrawn because there is no evidence to
 * re-offer them on.
 *
 * So this file does not demand parity. It PINS the exact set of keys each
 * locale is missing, and fails in BOTH directions:
 *
 *   - a NEW missing key is a regression — someone added English copy and left
 *     a locale behind;
 *   - a FIXED key that is still listed here is also a failure, so the list is
 *     forced to shrink as translations land instead of quietly outliving them.
 *
 * That second half is the whole point. An allowlist nobody is obliged to
 * prune becomes a permanent excuse, which is how a "temporary" gap reaches
 * its first anniversary.
 */

const DICTIONARIES: Record<Locale, unknown> = {
  en: enMessages,
  it: itMessages,
  id: idMessages,
  fr: frMessages,
  ru: ruMessages,
};

/**
 * Measured on 2026-08-31, the day `secondHome` was added to fr/ru. Every entry
 * is a key present in `en.json` and absent from that locale — a real gap where
 * the page falls back to English, not a design choice.
 *
 * `portal.*` is elided to the section name because the whole section is
 * absent. It is the client-portal login and password-recovery flow
 * (`/portal/login-upgraded`, `/portal/forgot-password`) — measured: 6
 * consumers, none of them reachable from any `/visa/*` route — so it is a
 * genuinely separate surface with its own owner, not part of this one.
 *
 * The five `common.consent.*` keys were the other half and are now CLOSED
 * (same day): that banner mounts on `/visa/second-home` and
 * `/visa/second-home/studio`, so it was rendering English to exactly the
 * French and Russian visitors those dictionaries had just been written for.
 * The ratchet is what forced the list to shrink here rather than outlive the
 * translation — it went red on `expected ['portal'] to deeply equal [...6]`
 * the moment the keys landed.
 */
const KNOWN_GAPS: Partial<Record<Locale, string[]>> = {
  fr: ["portal"],
  ru: ["portal"],
};

/** Every string leaf's dotted path. Arrays keep their index, so a shortened
 *  list in one locale is a missing key rather than a silent truncation. */
function leafPaths(
  node: unknown,
  prefix = "",
  out: Set<string> = new Set(),
): Set<string> {
  if (typeof node === "string") {
    out.add(prefix);
    return out;
  }
  if (Array.isArray(node)) {
    node.forEach((v, i) => leafPaths(v, `${prefix}[${i}]`, out));
    return out;
  }
  if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      leafPaths(v, prefix ? `${prefix}.${k}` : k, out);
    }
  }
  return out;
}

/** Collapse `portal.a.b` to `portal` when the ENTIRE section is absent, so a
 *  wholly-missing section is one ledger line instead of forty. */
function collapseWholeSections(missing: string[], dict: unknown): string[] {
  const top = new Set(Object.keys((dict ?? {}) as Record<string, unknown>));
  const out = new Set<string>();
  for (const path of missing) {
    const section = path.split(".")[0].split("[")[0];
    out.add(top.has(section) ? path : section);
  }
  return [...out].sort();
}

function gapsFor(locale: Locale): string[] {
  const en = leafPaths(DICTIONARIES.en);
  const mine = leafPaths(DICTIONARIES[locale]);
  return collapseWholeSections(
    [...en].filter((p) => !mine.has(p)),
    DICTIONARIES[locale],
  );
}

describe("locale key-set parity", () => {
  it("every SUPPORTED locale has a dictionary", () => {
    // `LOCALES` is the validation set: a `?lang=xx` URL is honored iff it
    // appears there, so a supported locale with no bundle is a 500 waiting
    // for the first visitor who saved that preference.
    for (const locale of LOCALES) {
      expect({ locale, hasDictionary: Boolean(DICTIONARIES[locale]) }).toEqual({
        locale,
        hasDictionary: true,
      });
    }
  });

  it("secondHome is present in EVERY locale, with the same keys as English", () => {
    // Stricter than the ratchet below, deliberately: this is the section the
    // fr/ru work of 2026-08-31 added, and it must not be allowed to decay
    // into a "known gap" later.
    const en = leafPaths((enMessages as { secondHome: unknown }).secondHome);
    expect(en.size).toBeGreaterThan(0);
    for (const locale of LOCALES) {
      const section = (DICTIONARIES[locale] as { secondHome?: unknown })
        .secondHome;
      expect({ locale, hasSecondHome: Boolean(section) }).toEqual({
        locale,
        hasSecondHome: true,
      });
      const mine = leafPaths(section);
      expect({ locale, missing: [...en].filter((p) => !mine.has(p)) }).toEqual({
        locale,
        missing: [],
      });
      expect({ locale, orphans: [...mine].filter((p) => !en.has(p)) }).toEqual({
        locale,
        orphans: [],
      });
    }
  });

  for (const locale of ["it", "id", "fr", "ru"] as const) {
    it(`${locale}: the gap against English is exactly the pinned set`, () => {
      // toEqual on a sorted array, not a subset check: a NEW gap fails, and
      // so does a gap that was closed but left in KNOWN_GAPS. The second
      // direction is what stops this list from becoming a permanent excuse.
      expect(gapsFor(locale)).toEqual([...(KNOWN_GAPS[locale] ?? [])].sort());
    });
  }

  // ── The consent banner specifically. Key parity above proves the keys
  //    EXIST; it cannot tell a translation from the English string pasted
  //    into a second file, and a banner that silently reads English is
  //    indistinguishable from a missing key to the visitor. `t()` falls back
  //    to `en` and then to the raw key path (src/i18n/index.tsx), so neither
  //    failure mode throws — nothing surfaces it but an assertion.
  const CONSENT_KEYS = [
    "text",
    "privacyPolicy",
    "and",
    "termsOfService",
    "dismiss",
  ] as const;

  for (const locale of ["it", "id", "fr", "ru"] as const) {
    it(`${locale}: the consent banner copy is present and actually translated`, () => {
      const en = (enMessages as Record<string, any>).common.consent;
      const mine = (DICTIONARIES[locale] as Record<string, any>).common
        ?.consent;
      expect({ locale, present: Boolean(mine) }).toEqual({
        locale,
        present: true,
      });
      // "and" is legitimately "e"/"dan"/"et"/"и" — short, but never the
      // English word. Every one of the five must differ from the English.
      const untranslated = CONSENT_KEYS.filter((k) => mine[k] === en[k]);
      expect({ locale, untranslated }).toEqual({ locale, untranslated: [] });
    });
  }
});

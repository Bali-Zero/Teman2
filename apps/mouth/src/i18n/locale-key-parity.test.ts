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
 * Measured on 2026-08-31, the day `secondHome` was added to fr/ru, and
 * emptied on 2026-09-03 when `portal` landed in both. Every entry is a key
 * present in `en.json` and absent from that locale — a real gap where the
 * page falls back to English, not a design choice.
 *
 * The list is EMPTY, and that is the state to defend: the ratchet's second
 * direction (a closed gap left listed here is also a failure) is what forced
 * it to shrink twice rather than outlive the translations. `common.consent.*`
 * closed 2026-08-31; `portal.*` closed 2026-09-03 — 12 leaf keys, the client
 * portal's login errors and password-recovery copy, which `types.ts` had been
 * describing as "complete" in fr/ru while the whole section was absent.
 *
 * Keep it empty by translating, never by re-adding a line here.
 */
const KNOWN_GAPS: Partial<Record<Locale, string[]>> = {};

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

  it("portal is present in EVERY locale, with the same keys as English", () => {
    // Same strictness as `secondHome` above, and for the same reason: this
    // section was a KNOWN_GAP in fr/ru for three days and the ratchet alone
    // would let it become one again — a section can be deleted wholesale and
    // reappear in KNOWN_GAPS with a plausible note. This assertion cannot be
    // satisfied that way: a missing section fails on `hasPortal`, and a
    // half-copied one fails on `missing`.
    const en = leafPaths((enMessages as { portal: unknown }).portal);
    expect(en.size).toBe(12);
    for (const locale of LOCALES) {
      const section = (DICTIONARIES[locale] as { portal?: unknown }).portal;
      expect({ locale, hasPortal: Boolean(section) }).toEqual({
        locale,
        hasPortal: true,
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

  // The `{{seconds}}` interpolation is the one token that must survive
  // translation verbatim — a locale that localizes the placeholder itself
  // renders the literal braces to the visitor instead of a number, and key
  // parity above cannot see it.
  for (const locale of LOCALES) {
    it(`${locale}: portal rate_limited keeps the {{seconds}} placeholder`, () => {
      const copy = (DICTIONARIES[locale] as Record<string, any>).portal.login
        .errors.rate_limited as string;
      expect({ locale, hasPlaceholder: copy.includes("{{seconds}}") }).toEqual({
        locale,
        hasPlaceholder: true,
      });
    });
  }

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

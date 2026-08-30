// Named `*Messages` — NOT `it`/`id` — because vitest's global `it()` test
// function lives in this module's scope too (globals: true); importing a
// default binding literally named `it` shadows it and every `it(...)` call
// below silently resolves to the JSON module instead of the test function.
import enMessages from "./locales/en.json";
import itMessages from "./locales/it.json";
import idMessages from "./locales/id.json";
import frMessages from "./locales/fr.json";
import ruMessages from "./locales/ru.json";

/**
 * W82 guard — locale-aware forbidden-claims sweep (2026-08-20 spec §6).
 *
 * The second-home landing carries hard claims discipline (research/
 * secondhome/e33-fact-registry.json + owner decisions 2026-07-23): no
 * BSI/sharia equivalence, no split deposits, no ITAP/KITAP conversion, no
 * "any bank" placement, no USD 1,500 figure, no fabricated E33S/E33R track.
 * The EN-only guard in page.test.tsx checks RENDERED English text; it is
 * blind to it.json/id.json entirely (W82's own signature — a guardian that
 * greps one language while the fact could go stale, or simply be wrong, in
 * another). This sweeps the `secondHome` subtree of all three dictionaries
 * with PER-LANGUAGE patterns, so translating the forbidden claim into it/id
 * does not let it slip past English-only substring matching.
 *
 * Word-boundary / phrase patterns, not bare substrings (family #3 in
 * cicatrix-superscar.md — `if "keyword" in s` traps on the word inside a
 * longer one). Patterns are the frozen spec's, verbatim.
 *
 * GUILT     — a planted forbidden phrase, per pattern per language, is caught.
 * INNOCENCE — the CURRENT dictionaries pass. If they did not, spec §6 says:
 *             stop and report the string verbatim — never silently "fix"
 *             vetted copy from inside a test file.
 */

type Locale = "en" | "it" | "id" | "fr" | "ru";

const RULES: Record<Locale, RegExp[]> = {
  en: [
    /USD\s*1,500\b/i,
    /\bany\s+bank\b/i,
    /\bguaranteed\b/i,
    /100%\s*approval/i,
    /\bautomatic\s+(?:ITAP|KITAP)\b/i,
    /\bsplit\s+deposit\b/i,
    /\bLPS\b/,
    /\bBSI\b/,
    /\bsharia\b/i,
    /\bE33S\b/,
    /\bE33R\b/,
  ],
  it: [
    /\bqualsiasi\s+banca\b/i,
    /\bgaranti(?:to|ta|amo)\b/i,
    /\bapprovazione\s+garantita/i,
    /\bautomatic[ao]\s+(?:ITAP|KITAP)/i,
    /\bdeposit[oi]\s+(?:frazionat|suddivis|multipl)/i,
    /\bLPS\b/,
    /\bBSI\b/,
    /1\.500\s*(?:USD|\$)|USD\s*1\.500/,
  ],
  id: [
    /\bbank\s+mana\s*pun\b/i,
    /\bdijamin\b/i,
    /\bjaminan\s+persetujuan/i,
    /\botomatis\s+(?:ITAP|KITAP)/i,
    /\bdeposito\s+(?:terpisah|dibagi|ganda)/i,
    /\bLPS\b/,
    /\bBSI\b/,
    // Scoped to currency context — a bare "1.500"/"1,500" elsewhere in the
    // subtree (a duration, a code) is not this claim.
    /(?:1\.500|1,500)\s*(?:USD|\$)|(?:USD|\$)\s*(?:1\.500|1,500)/,
  ],
  // fr/ru added 2026-08-31 with the secondHome dictionaries themselves. Two
  // things are different about these two languages and both are load-bearing:
  //
  // (a) THE SEPARATOR. French and Russian both use a SPACE for thousands
  //     (the copy reads `USD 130 000`, not `USD 130,000`), because a comma is
  //     their DECIMAL marker. So a superseded `USD 1,500` would land here as
  //     `USD 1 500` — and the en/it/id patterns, which only know `,` and `.`,
  //     would sail straight past it. The character class below therefore
  //     covers the plain space, NBSP (U+00A0) and the narrow no-break space
  //     (U+202F) that French typography actually produces, alongside `.`/`,`.
  //     This is the W82 under-match shape exactly: same claim, different
  //     orthography, guard blind.
  //
  // (b) THE APOSTROPHE. The French copy uses the straight `'` (47 occurrences,
  //     measured), but a later translator or a CMS paste can produce the
  //     typographic `\u2019`. Any pattern spanning an elision accepts both, or
  //     it silently stops matching the day the copy is retyped.
  fr: [
    /(?:1[\s\u00a0\u202f.,]?500)\s*(?:USD|\$)|(?:USD|\$)\s*(?:1[\s\u00a0\u202f.,]?500)/,
    /\b(?:n['\u2019]importe\s+quelle|une\s+quelconque|toute)\s+banque\b/i,
    /\bgaranti(?:e|s|es)?\b/i,
    /\bnous\s+garantissons\b/i,
    /\b(?:ITAP|KITAP)\s+automatique\b/i,
    /\bautomatiquement\s+(?:un\s+|une\s+)?(?:ITAP|KITAP)\b/i,
    /\bd[ée]p[ôo]ts?\s+(?:fractionn|divis|multipl|r[ée]parti)/i,
    /\bLPS\b/,
    /\bBSI\b/,
    /\b(?:charia|sharia)\b/i,
    /\bE33S\b/,
    /\bE33R\b/,
  ],
  // (c) THE WORD BOUNDARY. `\b` and `\w` in JavaScript are ASCII-only: `\w`
  //     is `[A-Za-z0-9_]`, so `\bдепозит` can NEVER match — there is no
  //     ASCII word character adjacent to a Cyrillic one for the boundary to
  //     sit on. Written the obvious way, every Cyrillic pattern below is a
  //     guard that looks armed and cannot fire, which is W82 in its purest
  //     form: it would have passed INNOCENCE on the live copy for the same
  //     reason it passed on a planted claim. Caught by this file's own GUILT
  //     test, not by review. The cure is a Unicode-aware boundary
  //     (`(?<![\p{L}])` with the `u` flag) and `\p{L}` in place of `\w`.
  ru: [
    /(?:1[\s\u00a0\u202f.,]?500)\s*(?:USD|\$)|(?:USD|\$)\s*(?:1[\s\u00a0\u202f.,]?500)/,
    /(?<![\p{L}])люб(?:ой|ом|ого|ые|ых)\s+банк/iu,
    /(?<![\p{L}])гарантир\p{L}*/iu,
    /(?<![\p{L}])гаранти(?:я|ю|и)\s+одобрения/iu,
    /(?<![\p{L}])автоматическ\p{L}*\s+(?:ITAP|KITAP)(?![\p{L}])/iu,
    /(?<![\p{L}])(?:раздел[её]нн\p{L}*|разбит\p{L}*)\s+депозит/iu,
    /(?<![\p{L}])депозит\p{L}*\s+(?:раздел|разбит|в\s+нескольких)/iu,
    /\bLPS\b/,
    /\bBSI\b/,
    /(?<![\p{L}])(?:шариат\p{L}*|sharia)(?![\p{L}])/iu,
    /\bE33S\b/,
    /\bE33R\b/,
  ],
};

const DICTIONARIES: Record<Locale, unknown> = {
  en: enMessages,
  it: itMessages,
  id: idMessages,
  fr: frMessages,
  ru: ruMessages,
};

/** Recursively collects every string leaf under a JSON subtree. */
function collectStrings(node: unknown, out: string[]): void {
  if (typeof node === "string") {
    out.push(node);
    return;
  }
  if (Array.isArray(node)) {
    for (const item of node) collectStrings(item, out);
    return;
  }
  if (node && typeof node === "object") {
    for (const value of Object.values(node as Record<string, unknown>)) {
      collectStrings(value, out);
    }
  }
}

interface Hit {
  pattern: string;
  value: string;
}

function sweep(subtree: unknown, patterns: RegExp[]): Hit[] {
  const strings: string[] = [];
  collectStrings(subtree, strings);
  const hits: Hit[] = [];
  for (const value of strings) {
    for (const pattern of patterns) {
      if (pattern.test(value)) {
        hits.push({ pattern: pattern.toString(), value });
      }
    }
  }
  return hits;
}

function secondHomeOf(dict: unknown): unknown {
  return (dict as { secondHome?: unknown }).secondHome;
}

describe("secondHome dictionaries — W82 locale-aware forbidden-claims sweep", () => {
  // ── INNOCENCE — current vetted copy passes, in every language ──────────
  (Object.keys(RULES) as Locale[]).forEach((locale) => {
    it(`INNOCENCE (${locale}): the current secondHome dictionary has no forbidden claim`, () => {
      const hits = sweep(secondHomeOf(DICTIONARIES[locale]), RULES[locale]);
      // Report verbatim rather than silently "fixing" vetted copy (spec §6).
      expect(hits).toEqual([]);
    });
  });

  // ── GUILT — one planted phrase per pattern, per language, is caught ────
  it("GUILT (en): each forbidden pattern fires on a planted phrase", () => {
    const fixture = {
      faq: {
        p1: "Deposit USD 1,500 today.",
        p2: "Works with any bank in Indonesia.",
        p3: "Your approval is guaranteed.",
        p4: "100% approval on the first try.",
        p5: "Automatic ITAP after 3 years.",
        p6: "We offer a split deposit option.",
        p7: "Protected under LPS insurance.",
        p8: "BSI sharia-compliant deposit accepted.",
        p9: "Apply for E33S today.",
        p10: "Apply for E33R today.",
      },
    };
    const hits = sweep(fixture, RULES.en);
    // At least one hit per pattern in the ruleset.
    for (const pattern of RULES.en) {
      expect(hits.some((h) => h.pattern === pattern.toString())).toBe(true);
    }
  });

  it("GUILT (it): each forbidden pattern fires on a planted phrase", () => {
    const fixture = {
      faq: {
        p1: "Va bene qualsiasi banca indonesiana.",
        p2: "Ti garantiamo l'approvazione.",
        p3: "Approvazione garantita in 3 giorni.",
        p4: "Conversione automatica ITAP dopo 3 anni.",
        p5: "Deposito frazionato in più banche.",
        p6: "Coperto da LPS.",
        p7: "Accettiamo BSI sharia.",
        p8: "USD 1.500 di anticipo.",
      },
    };
    const hits = sweep(fixture, RULES.it);
    for (const pattern of RULES.it) {
      expect(hits.some((h) => h.pattern === pattern.toString())).toBe(true);
    }
  });

  it("STRUCTURAL: no Cyrillic pattern relies on an ASCII-only \\b or \\w", () => {
    // The trap this file already fell into once: in JavaScript `\w` is
    // `[A-Za-z0-9_]` and `\b` is defined in terms of it, so `\bдепозит`
    // matches NOTHING — a pattern that reads like a guard and can never
    // fire. It survives INNOCENCE for the same reason it fails GUILT, so a
    // reviewer scanning the list sees nothing wrong.
    //
    // Asserted on the pattern SOURCE rather than on behaviour, because the
    // behavioural test only covers the phrasings someone thought to plant;
    // this covers every pattern, including ones added later.
    const CYRILLIC = /[\u0400-\u04ff]/;
    for (const locale of ["fr", "ru"] as const) {
      for (const pattern of RULES[locale]) {
        const src = pattern.source;
        if (!CYRILLIC.test(src)) continue;
        // A failure prints this object, so it names the offending pattern:
        // an ASCII \\b or \\w beside Cyrillic can never match, and \\p{L} is
        // inert without the u flag.
        expect({
          pattern: String(pattern),
          asciiBoundary: /\\[bw]/.test(src),
          unicodeFlag: pattern.flags.includes("u"),
        }).toEqual({
          pattern: String(pattern),
          asciiBoundary: false,
          unicodeFlag: true,
        });
      }
    }
  });

  it("GUILT (fr): each forbidden pattern fires on a planted phrase", () => {
    const fixture = {
      faq: {
        // NOTE the SPACE separator: this is the exact shape a superseded
        // figure takes in French copy, and the one the en/it/id patterns
        // cannot see.
        p1: "Un dépôt de USD 1 500 suffit.",
        p2: "Vous pouvez utiliser n\u2019importe quelle banque indonésienne.",
        p3: "Votre approbation est garantie.",
        p4: "Nous garantissons le résultat.",
        p5: "KITAP automatique après trois ans.",
        p6: "Vous obtenez automatiquement un ITAP.",
        p7: "Nous proposons un dépôt fractionné sur deux banques.",
        p8: "Couvert par la LPS.",
        p9: "Dépôt BSI accepté.",
        p10: "Compte conforme à la charia.",
        p11: "Demandez le E33S dès aujourd\u2019hui.",
        p12: "Demandez le E33R dès aujourd\u2019hui.",
      },
    };
    const hits = sweep(fixture, RULES.fr);
    for (const pattern of RULES.fr) {
      expect(hits.some((h) => h.pattern === pattern.toString())).toBe(true);
    }
  });

  it("GUILT (fr): the straight apostrophe is caught too, not only the typographic one", () => {
    // The live copy uses ' (47 occurrences, measured). A pattern written
    // against \u2019 alone would be innocent on a planted claim in the very
    // orthography the dictionary actually uses.
    const hits = sweep({ p: "Utilisez n'importe quelle banque." }, RULES.fr);
    expect(hits.length).toBeGreaterThan(0);
  });

  it("GUILT (ru): each forbidden pattern fires on a planted phrase", () => {
    const fixture = {
      faq: {
        p1: "Достаточно депозита USD 1 500.",
        p2: "Подойдёт любой банк Индонезии.",
        p3: "Мы гарантируем одобрение.",
        p4: "Гарантия одобрения за три дня.",
        p5: "Автоматический KITAP через три года.",
        p6: "Мы предлагаем разделённый депозит.",
        p7: "Депозит разделён между двумя банками.",
        p8: "Покрывается LPS.",
        p9: "Принимается депозит BSI.",
        p10: "Счёт соответствует шариату.",
        p11: "Подайте на E33S сегодня.",
        p12: "Подайте на E33R сегодня.",
      },
    };
    const hits = sweep(fixture, RULES.ru);
    for (const pattern of RULES.ru) {
      expect(hits.some((h) => h.pattern === pattern.toString())).toBe(true);
    }
  });

  it("GUILT (fr+ru): the space-separated superseded figure is caught in BOTH", () => {
    // The whole reason these two rulesets are not copies of the en one.
    for (const locale of ["fr", "ru"] as const) {
      for (const spaced of [
        "USD 1 500",
        "USD 1\u00a0500",
        "USD 1\u202f500",
        "1 500 USD",
      ]) {
        const hits = sweep({ p: `Le montant est ${spaced}.` }, RULES[locale]);
        expect({ locale, spaced, caught: hits.length > 0 }).toEqual({
          locale,
          spaced,
          caught: true,
        });
      }
    }
  });

  it("INNOCENCE (fr+ru): the LEGITIMATE figures are not mistaken for the superseded one", () => {
    // The money pattern must fire on 1 500 and nothing else. USD 130 000,
    // USD 1 000 000, USD 50 000 and USD 3 000 all appear in the live copy
    // with the same space separator; a pattern anchored loosely on "1" and
    // a space would swallow USD 1 000 000 and turn the guard into noise.
    for (const locale of ["fr", "ru"] as const) {
      for (const ok of [
        "USD 130 000",
        "USD 1 000 000",
        "USD 50 000",
        "USD 3 000",
      ]) {
        const hits = sweep({ p: `Le montant est ${ok}.` }, RULES[locale]);
        expect({ locale, figure: ok, hits }).toEqual({
          locale,
          figure: ok,
          hits: [],
        });
      }
    }
  });

  it("GUILT (id): each forbidden pattern fires on a planted phrase", () => {
    const fixture = {
      faq: {
        p1: "Bisa pakai bank mana pun.",
        p2: "Kami dijamin approve.",
        p3: "Ada jaminan persetujuan cepat.",
        p4: "Konversi otomatis ITAP setelah 3 tahun.",
        p5: "Deposito terpisah diperbolehkan.",
        p6: "Dilindungi LPS.",
        p7: "BSI syariah diterima.",
        p8: "USD 1.500 saja.",
      },
    };
    const hits = sweep(fixture, RULES.id);
    for (const pattern of RULES.id) {
      expect(hits.some((h) => h.pattern === pattern.toString())).toBe(true);
    }
  });

  // ── INNOCENCE (guard-conformance twin) — a neighbouring legitimate
  // phrase must NOT trip the scanner (family #3's "guilt+innocence" pair).
  it("INNOCENCE: a legitimate neighbouring phrase does not trip the scanner", () => {
    const fixture = {
      faq: {
        clean_en:
          "A deposit in your own name at a state-owned (BUMN) Indonesian bank.",
        clean_it:
          "Un deposito intestato a te presso una banca statale indonesiana.",
        clean_id: "Deposito atas nama sendiri di bank BUMN Indonesia.",
      },
    };
    expect(sweep(fixture, RULES.en)).toEqual([]);
    expect(sweep(fixture, RULES.it)).toEqual([]);
    expect(sweep(fixture, RULES.id)).toEqual([]);
  });
});

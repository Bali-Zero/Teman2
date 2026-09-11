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

// ── The superseded USD 1,500 figure, in every orthography these five
//    locales produce. ONE pattern shared by all of them, for two reasons.
//
//    (a) It used to be five separate patterns and they had DRIFTED apart:
//        `en` knew only `USD 1,500` (comma, currency first), `it`/`id` only
//        the period form, and only fr/ru knew the space separator. So
//        `1.500 USD` written in English copy was invisible to the English
//        ruleset while being caught in Italian — the same claim, guarded in
//        one language and not its neighbour.
//    (b) It was UNANCHORED. `USD 1 500 000` is a legitimate figure and
//        `11 500 USD` a plausible one, and both matched. The digit
//        lookarounds below are what make this fire on 1 500 and nothing
//        else; the INNOCENCE test at the bottom pins that.
const SEP = "[\\s\\u00a0\\u202f.,]";
//    (c) THE CENTS. The trailing lookahead that (correctly) rejects
//        `USD 1 500 000` as a THOUSANDS continuation also rejected
//        `USD 1,500.00` — which is not a different number, it is the
//        superseded figure written the way an English invoice writes it.
//        `USD 1.500,00` and `$1 500,50` are the same figure in the other
//        four locales' notation. All three were measured evading.
//        The two cases are separable by DIGIT COUNT, which is the whole
//        trick: a separator followed by exactly TWO digits and then a
//        non-digit is a cents group and the amount is still 1 500; a
//        separator followed by THREE is another thousands group and the
//        amount is 1 500 000. So consume an optional cents group first,
//        then refuse a thousands continuation.
const N1500 = `(?<!\\d)1${SEP}?500(?:${SEP}\\d{2}(?!\\d))?(?!${SEP}?\\d)`;
const SUPERSEDED_1500 = new RegExp(
  `${N1500}\\s*(?:USD|\\$)|(?:USD|\\$)\\s*${N1500}`,
  "i",
);

const RULES: Record<Locale, RegExp[]> = {
  en: [
    SUPERSEDED_1500,
    /\bany\s+bank\b/i,
    /\bguaranteed\b/i,
    /100%\s*approval/i,
    /\bautomatic\s+(?:ITAP|KITAP)\b/i,
    /\bsplit\s+deposit\b/i,
    /\bLPS\b/i,
    /\bBSI\b/i,
    /\b(?:sharia|syariah)\b/i,
    /\bE33S\b/i,
    /\bE33R\b/i,
  ],
  it: [
    /\bqualsiasi\s+banca\b/i,
    /\bgaranti(?:to|ta|amo)\b/i,
    /\bapprovazione\s+garantita/i,
    /\bautomatic[ao]\s+(?:ITAP|KITAP)/i,
    /\bdeposit[oi]\s+(?:frazionat|suddivis|multipl)/i,
    /\bLPS\b/i,
    /\bBSI\b/i,
    // it/id watched neither the sharia claim nor the two fabricated codes,
    // which en/fr/ru all did — the same claim guarded in three languages and
    // open in two. These literals are language-independent, so there is no
    // translation judgement in adding them.
    /\b(?:sharia|syariah)\b/i,
    /\bE33S\b/i,
    /\bE33R\b/i,
    SUPERSEDED_1500,
  ],
  id: [
    /\bbank\s+mana\s*pun\b/i,
    /\bdijamin\b/i,
    /\bjaminan\s+persetujuan/i,
    /\botomatis\s+(?:ITAP|KITAP)/i,
    /\bdeposito\s+(?:terpisah|dibagi|ganda)/i,
    /\bLPS\b/i,
    /\bBSI\b/i,
    /\b(?:sharia|syariah)\b/i,
    /\bE33S\b/i,
    /\bE33R\b/i,
    SUPERSEDED_1500,
  ],
  // fr/ru added 2026-08-31 with the secondHome dictionaries themselves. Two
  // things are different about these two languages and both are load-bearing:
  //
  // (a) THE SEPARATOR. French and Russian both use a SPACE for thousands
  //     (the copy reads `USD 130 000`, not `USD 130,000`), because a comma is
  //     their DECIMAL marker, so a superseded `USD 1,500` lands here as
  //     `USD 1 500`. That is why SUPERSEDED_1500 above covers the plain
  //     space, NBSP (U+00A0) and the narrow no-break space (U+202F) that
  //     French typography actually produces, alongside `.`/`,` — and why it
  //     is now shared with en/it/id rather than living only here: the same
  //     claim in a different orthography is the W82 under-match shape, and it
  //     does not stop being one when it is written in English.
  //
  // (b) THE APOSTROPHE. The French copy uses the straight `'` (47 occurrences,
  //     measured), but a later translator or a CMS paste can produce the
  //     typographic `\u2019`. Any pattern spanning an elision accepts both, or
  //     it silently stops matching the day the copy is retyped.
  fr: [
    SUPERSEDED_1500,
    /\b(?:n['\u2019]importe\s+quelle|une\s+quelconque|toute)\s+banque\b/i,
    /\bgaranti(?:e|s|es)?\b/i,
    /\bnous\s+garantissons\b/i,
    /\b(?:ITAP|KITAP)\s+automatique\b/i,
    /\bautomatiquement\s+(?:un\s+|une\s+)?(?:ITAP|KITAP)\b/i,
    /\bd[ée]p[ôo]ts?\s+(?:fractionn|divis|multipl|r[ée]parti)/i,
    /\bLPS\b/i,
    /\bBSI\b/i,
    /\b(?:charia|sharia|syariah)\b/i,
    /\bE33S\b/i,
    /\bE33R\b/i,
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
    SUPERSEDED_1500,
    /(?<![\p{L}])люб(?:ой|ом|ого|ые|ых)\s+банк/iu,
    /(?<![\p{L}])гарантир\p{L}*/iu,
    /(?<![\p{L}])гаранти(?:я|ю|и)\s+одобрения/iu,
    /(?<![\p{L}])автоматическ\p{L}*\s+(?:ITAP|KITAP)(?![\p{L}])/iu,
    /(?<![\p{L}])(?:раздел[её]нн\p{L}*|разбит\p{L}*)\s+депозит/iu,
    /(?<![\p{L}])депозит\p{L}*\s+(?:раздел|разбит|в\s+нескольких)/iu,
    /\bLPS\b/i,
    /\bBSI\b/i,
    // Russian copy routinely transliterates a foreign acronym rather than
    // keeping it in Latin script. `\bLPS\b` cannot see ЛПС at all — it is a
    // script-level miss, not a case one, so /i does not reach it.
    /(?<![\p{L}])(?:ЛПС|БСИ)(?![\p{L}])/iu,
    /(?<![\p{L}])(?:шариат\p{L}*|sharia|syariah)(?![\p{L}])/iu,
    /\bE33S\b/i,
    /\bE33R\b/i,
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
        p9: "Conto conforme alla syariah.",
        p10: "Richiedi l'E33S oggi stesso.",
        p11: "Richiedi l'E33R oggi stesso.",
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
        p13: "Депозит покрывается по программе ЛПС.",
      },
    };
    const hits = sweep(fixture, RULES.ru);
    for (const pattern of RULES.ru) {
      expect(hits.some((h) => h.pattern === pattern.toString())).toBe(true);
    }
  });

  it("GUILT (all locales): the superseded figure is caught in every orthography", () => {
    // One table, five rulesets. Before SUPERSEDED_1500 was shared, this
    // table could not have been written: each locale caught its own
    // separator and was blind to the others, so `1.500 USD` in English copy
    // and `USD 1,500` in French copy both walked through.
    for (const locale of Object.keys(RULES) as Locale[]) {
      for (const spelled of [
        "USD 1,500",
        "USD 1.500",
        "USD 1 500",
        "USD 1\u00a0500",
        "USD 1\u202f500",
        "1 500 USD",
        "1.500 USD",
        "1,500 USD",
        // lowercase ticker — the /i flag, not the separator, is what
        // catches this one.
        "usd 1 500",
        "$1,500",
        "1 500 $",
        // ── cents. Not a different number: the superseded figure written
        //    the way an invoice writes it, in each locale's notation.
        "USD 1,500.00",
        "USD 1.500,00",
        "1.500,00 USD",
        "$1 500,50",
        "1 500,00 USD",
        // the Indonesian/Dutch "and no cents" dash
        "USD 1.500,-",
      ]) {
        const hits = sweep({ p: `Total: ${spelled}.` }, RULES[locale]);
        expect({ locale, spelled, caught: hits.length > 0 }).toEqual({
          locale,
          spelled,
          caught: true,
        });
      }
    }
  });

  it("INNOCENCE (all locales): the legitimate figures are not mistaken for it", () => {
    // The money pattern must fire on 1 500 and nothing else. USD 130 000,
    // USD 1 000 000, USD 50 000 and USD 3 000 all appear in the live copy.
    // The last two rows are the ones the UNANCHORED pattern got wrong:
    // `USD 1 500 000` and `11 500 USD` both contain the digits 1-500 and
    // are not the superseded figure.
    for (const locale of Object.keys(RULES) as Locale[]) {
      for (const ok of [
        "USD 130,000",
        "USD 130.000",
        "USD 130 000",
        "USD 1,000,000",
        "USD 1.000.000",
        "USD 1 000 000",
        "USD 50 000",
        "USD 3 000",
        "USD 1 500 000",
        "11 500 USD",
        // A THIRD digit after the separator is another thousands group, not
        // cents — that is the only thing separating these from the rows
        // above, and it is why the cents group demands exactly two.
        "USD 1.500.000",
        "1,500,000 USD",
        "USD 1,500.000",
        // digits on the other side: the lookbehind and lookahead each own
        // one of these.
        "USD 21,500",
        "USD 1,5001",
      ]) {
        const hits = sweep({ p: `Total: ${ok}.` }, RULES[locale]);
        expect({ locale, figure: ok, hits }).toEqual({
          locale,
          figure: ok,
          hits: [],
        });
      }
    }
  });

  it("STRUCTURAL: every pattern in every ruleset is case-insensitive", () => {
    // `/\bLPS\b/` without the flag is a guard a translator disarms by
    // writing `lps`. Twenty patterns across the five locales were missing
    // it — including all four brand/code literals in all five, and three of
    // the five money patterns — so a claim written in lower case was
    // invisible everywhere at once. Asserted over the whole ruleset rather
    // than the twenty known cases, so a pattern added later inherits it.
    const caseSensitive: string[] = [];
    for (const locale of Object.keys(RULES) as Locale[]) {
      for (const pattern of RULES[locale]) {
        if (!pattern.flags.includes("i")) {
          caseSensitive.push(`${locale}: ${String(pattern)}`);
        }
      }
    }
    expect(caseSensitive).toEqual([]);
  });

  // ── STRUCTURAL: the language-INDEPENDENT tokens are watched everywhere.
  //    LPS, BSI, E33S, E33R and sharia/syariah read the same in all five
  //    languages, so there is no translation judgement involved in watching
  //    them — yet it/id watched neither the codes nor the sharia claim,
  //    which is how a ruleset drifts: nobody diffs five arrays by eye. This
  //    test is the diff.
  const UNIVERSAL_TOKENS = [
    "LPS",
    "lps",
    "BSI",
    "bsi",
    "E33S",
    "e33s",
    "E33R",
    "e33r",
    "sharia",
    "Sharia",
    "syariah",
    "Syariah",
  ];
  it("STRUCTURAL (ru): the transliterated acronyms are watched too", () => {
    // Kept separate from UNIVERSAL_TOKENS because ЛПС/БСИ are a RUSSIAN
    // spelling of a Latin acronym, not a language-independent literal.
    // It also needs to be its own assertion: the GUILT test above cannot
    // catch a pattern being DELETED — it iterates over the patterns that
    // exist, so removing one removes its own obligation to fire, and the
    // planted phrase for it becomes inert copy nobody checks. Measured:
    // deleting this rule left all 21 tests green until this test existed.
    for (const token of ["ЛПС", "лпс", "БСИ", "бси"]) {
      const hits = sweep({ p: `Депозит и ${token} здесь.` }, RULES.ru);
      expect({ token, caught: hits.length > 0 }).toEqual({
        token,
        caught: true,
      });
    }
  });

  (Object.keys(RULES) as Locale[]).forEach((locale) => {
    it(`STRUCTURAL (${locale}): every language-independent token is watched, in either case`, () => {
      const missed = UNIVERSAL_TOKENS.filter(
        (token) =>
          sweep({ p: `Note: ${token} here.` }, RULES[locale]).length === 0,
      );
      expect({ locale, missed }).toEqual({ locale, missed: [] });
    });
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
        p9: "Ajukan E33S sekarang.",
        p10: "Ajukan E33R sekarang.",
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

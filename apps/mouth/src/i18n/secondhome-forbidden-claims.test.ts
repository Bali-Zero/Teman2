// Named `*Messages` — NOT `it`/`id` — because vitest's global `it()` test
// function lives in this module's scope too (globals: true); importing a
// default binding literally named `it` shadows it and every `it(...)` call
// below silently resolves to the JSON module instead of the test function.
import enMessages from "./locales/en.json";
import itMessages from "./locales/it.json";
import idMessages from "./locales/id.json";

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

type Locale = "en" | "it" | "id";

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
};

const DICTIONARIES: Record<Locale, unknown> = {
  en: enMessages,
  it: itMessages,
  id: idMessages,
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

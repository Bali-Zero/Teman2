// =============================================================================
// PROSE PIN GATE — the aggregate numbers we PUBLISH must agree with the canonical.
//
// WHY THIS EXISTS. `kbli-canonical-pins.test.ts` guards the pins that live in
// JSON. This file guards the ones that live in sentences, which is where they
// actually reach a client.
//
// On 2026-08-11 the article `the-honest-map-blocked-bali-codes` was published
// with a body that corrected itself — "518 of 1,559 — 33.2%, not 39%" — and a
// conclusion that still carried the retracted figure: "backed by 465 counted
// codes". The survivor count in the same section was derived from the retracted
// one (1,559 − 465 = 1,094), so the published article asserted
// 518 + 1,094 = 1,612 against a 1,559-row dataset, in three languages. The
// article's own thesis is that "the moment a number can't be reproduced from
// the file, it stops being journalism and starts being a rumour" — and nothing
// on disk was able to notice that its last paragraph had become exactly that.
//
// A number in prose is a derived pin like any other: it goes stale the instant a
// cure rewrites the dataset, and unlike a JSON pin no compiler bumps it. So it
// gets asserted here, in the same required suite (`tests.yml`, no path filter)
// that already carries the JSON pins — no new required context, per Merge-OS
// §3.8's rule against governing 26 required checks by adding a 27th.
//
// WHAT THIS DOES NOT DO. It does not parse prose for "any number". A bare digit
// grep over articles is how `lint_retracted_claims.py` learned its lesson, and
// how this gate's own first draft accused an unrelated 29.8% corporate-tax rate
// in a CV-structure article. Every claim below is ANCHORED to the sentence that
// carries it, and every expected value is RECOMPUTED from the dataset — never
// hard-coded, or the gate would only pin the article to a past reading.
//
// REMEDIATION when this fails: the dataset moved. Update the sentence in each
// language file to the recomputed value the failure message prints. Do not
// update this test — it has no numbers of its own to update.
//
// EN IS SENTENCE-REGEX; IT/ID ARE POSITIONAL (rewritten 2026-09-15, Codex
// GPT-5.6-sol xhigh adversarial review, W-H PR-6). The hourly translator
// rewords the it/id articles on every run, so a probe anchored to exact
// wording ("codici senza flag di blocco" → "codici non riportano il flag
// bloccato" …) turns into a treadmill a fresh reword keeps breaking; EN stays
// sentence-regex because it is the human-authored source, never re-translated.
//
// The FIRST it/id design (character-window "these numbers occur near each
// other, in order, somewhere in the file") had two holes the review proved by
// mutation: (1) BLOCKER — `text.indexOf()` matches a smaller expected number
// INSIDE a larger one ("373" inside a mutated "1373"), so six simultaneously
// wrong category counts stayed green; (2) the "try every occurrence of the
// first number" retry let a probe validate against the WRONG occurrence —
// mutating the headline's 519→518, the correction paragraph's 33,3→33,2 and
// the closing sentence's 519→518 all at once stayed green because an
// untouched, genuinely-correct "519"/"33,3" survived at a DIFFERENT sentence
// and the probe happily matched that one instead.
//
// The cure below replaces character-window matching with POSITION: every
// number token in the article body (frontmatter excluded) is extracted once,
// in reading order, as a maximal digit run ("1.373" is one token, never "1"
// + "373" — so "373" can never match inside it), and each claim is pinned to
// the token's OCCURRENCE INDEX, verified once against the live it/id files
// (`numberTokens()` dump, 2026-09-15) and IDENTICAL in both languages because
// the translator reorders nothing, only rewords. A wrong-paragraph swap can
// no longer hide behind a correct sibling occurrence, because each pin reads
// its own index and nothing else's.
// =============================================================================

import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const REPO_ROOT = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  "../../../..",
);

const CANONICAL = path.join(
  REPO_ROOT,
  "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",
);

const ARTICLE_DIR = path.join(
  REPO_ROOT,
  "apps/mouth/src/content/articles/business_regulations",
);
const ARTICLE_BASE = "the-honest-map-blocked-bali-codes";

const ARTICLE_FILES = [
  { lang: "en", file: `${ARTICLE_BASE}.mdx` },
  { lang: "it", file: `${ARTICLE_BASE}.it.mdx` },
  { lang: "id", file: `${ARTICLE_BASE}.id.mdx` },
];

type Row = {
  l4_bali?: { blocked?: boolean; status?: string };
  pma_status?: string;
  pma_max_asing?: number;
};

/** The one place any expected number in this file comes from. */
function countFromCanonical() {
  const raw = JSON.parse(fs.readFileSync(CANONICAL, "utf-8")) as {
    data: Row[];
  };
  const rows = raw.data;
  const total = rows.length;
  const blocked = rows.filter((r) => r.l4_bali?.blocked === true).length;
  return {
    total,
    blocked,
    open: total - blocked,
    pct: Math.round((blocked / total) * 1000) / 10,
  };
}

/**
 * The published "the-honest-map" article breaks its 519-blocked headline down
 * into six category counts, and two of those (TERTUTUP, "the remainder")
 * further split into sub-counts the prose also states. This recomputes every
 * one of them so the prose can be pinned to the ACTUAL per-status breakdown,
 * not a copy that drifts the moment a cure changes one status.
 */
function countBreakdown() {
  const raw = JSON.parse(fs.readFileSync(CANONICAL, "utf-8")) as {
    data: Row[];
  };
  const rows = raw.data;
  const blockedRows = rows.filter((r) => r.l4_bali?.blocked === true);
  const byStatus = (status: string) =>
    blockedRows.filter((r) => r.l4_bali?.status === status);

  const riskClassRows = byStatus("BLOCCATO_CLASSE_RISCHIO");
  const riskClass = riskClassRows.length;
  // "all but four nationally open" (Codex review finding 2): among the
  // risk-class-blocked rows, how many carry a nationally OPEN catalogue
  // status? The complement is the spelled-out "four".
  const riskClassNationallyOpen = riskClassRows.filter(
    (r) => r.pma_status === "TERBUKA",
  ).length;
  const riskClassNotNationallyOpen = riskClass - riskClassNationallyOpen;

  const moratorium = byStatus("CHIUSO_MORATORIA_BALI").length;

  const tertutupRows = byStatus("TERTUTUP");
  const tertutup = tertutupRows.length;
  // "62 of them carry 0% foreign ownership... the other 6 are the trap"
  // (Codex review finding 2): split by the catalogue-level pma_max_asing.
  const tertutupZero = tertutupRows.filter((r) => r.pma_max_asing === 0).length;
  const tertutupNonZero = tertutup - tertutupZero;

  const nonClassificabile = byStatus("NON_CLASSIFICABILE").length;
  const pmaNoBesar = byStatus("CHIUSO_PMA_NO_BESAR").length;

  // The article's "6 — the remainder" line groups every other blocked
  // status, printed as "2 ... 2 ... 2" (the last "2" is 1 CHIUSO_BALI + 1
  // CHIUSO_BALI_PROPOSTO, worded as "70209 and one proposed" — never a
  // literal digit "1", so there is nothing to pin below that sum).
  const regolatoreSettoriale = byStatus("CHIUSO_REGOLATORE_SETTORIALE").length;
  const dipendeScopeBlockedTrue = byStatus("BLOCCATO_DIPENDE_SCOPE").length;
  const chiusoBali = byStatus("CHIUSO_BALI").length;
  const chiusoBaliProposto = byStatus("CHIUSO_BALI_PROPOSTO").length;
  const baliClosuresSum = chiusoBali + chiusoBaliProposto;
  const smallRemainder =
    regolatoreSettoriale + dipendeScopeBlockedTrue + baliClosuresSum;

  const scopeDependentNotBlocked = rows.filter(
    (r) =>
      r.l4_bali?.status === "BLOCCATO_DIPENDE_SCOPE" &&
      r.l4_bali?.blocked === false,
  ).length;

  return {
    riskClass,
    riskClassNationallyOpen,
    riskClassNotNationallyOpen,
    moratorium,
    tertutup,
    tertutupZero,
    tertutupNonZero,
    nonClassificabile,
    pmaNoBesar,
    regolatoreSettoriale,
    dipendeScopeBlockedTrue,
    baliClosuresSum,
    smallRemainder,
    scopeDependentNotBlocked,
  };
}

/** `1041` → `1,041` (en) / `1.041` (it, id). */
const group = (n: number, sep: string) =>
  n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, sep);

/** `33.3` → `33,3` — the IT/ID decimal-comma reading of a percentage that is
 * always computed as a plain `X.Y` number (see `countFromCanonical().pct`). */
const pctComma = (pct: number) => pct.toFixed(1).replace(".", ",");

/** English words for the small counts this article ever spells out instead
 * of printing as a digit ("all but four nationally open"). Indexed by the
 * computed value, so the word is still DERIVED, never a bare hard-coded
 * "four" compared against a bare hard-coded "four". */
const SMALL_NUMBER_WORDS = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
];

// -----------------------------------------------------------------------
// POSITIONAL NUMBER MATCHING (it/id) — see the file header for why this
// replaced character-window matching on 2026-09-15.
// -----------------------------------------------------------------------

/** A maximal run of digits, optionally with internal `.`/`,` separators —
 * "1.373" is ONE token, never "1" + "373". Equality against an expected
 * formatted number is always on the WHOLE token below, so an expected "373"
 * never matches inside an actual "1373" (Codex review, BLOCKER finding 1). */
const NUMBER_TOKEN_SOURCE = String.raw`\d(?:[\d.,]*\d)?`;

/** Everything after the frontmatter's closing `---` delimiter. Frontmatter
 * carries its own numbers (`publishedAt`, `readingTime`, `aiConfidenceScore`)
 * that are not prose and must never be counted as an "occurrence". */
function articleBody(text: string): string {
  const first = text.indexOf("---");
  if (first === -1) return text;
  const second = text.indexOf("---", first + 3);
  if (second === -1) return text;
  return text.slice(second + 3);
}

/** The `n`th (1-indexed) number token in `text`'s BODY, in reading order, or
 * `null` if the body has fewer than `n`. This is POSITION, not a value
 * search: two genuine mentions of the same figure (e.g. "1,559" appears 4
 * times in this article) are different occurrences, and a pin on one index
 * is blind to what happens at another — which is exactly what let a
 * wrong-paragraph mutation of ONE occurrence hide behind a correct sibling
 * under the old "search anywhere, try every start" design (Codex review,
 * finding 1, second reproduction). */
function nthNumberToken(text: string, n: number): string | null {
  const body = articleBody(text);
  const re = new RegExp(NUMBER_TOKEN_SOURCE, "g");
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(body)) !== null) {
    i++;
    if (i === n) return m[0];
  }
  return null;
}

/** How many number tokens the body carries — asserted before the positional
 * pins below run, so a reword that ADDS or DROPS a numeral fails loudly as
 * "the body doesn't have as many numbers as the map expects" rather than
 * silently reading every pin below the shift at the wrong occurrence. */
function numberTokenCount(text: string): number {
  const body = articleBody(text);
  const re = new RegExp(NUMBER_TOKEN_SOURCE, "g");
  return (body.match(re) ?? []).length;
}

/** Test-only: replace the `occurrence`th number token with `replacement`,
 * leaving every OTHER mention — including other genuine occurrences of the
 * SAME figure — untouched. Used below to reproduce the Codex review's exact
 * mutations as guilt cases against the new positional mechanism. */
function spliceNumberAt(
  text: string,
  occurrence: number,
  replacement: string,
): string {
  const body = articleBody(text);
  const bodyStart = text.length - body.length;
  const re = new RegExp(NUMBER_TOKEN_SOURCE, "g");
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(body)) !== null) {
    i++;
    if (i === occurrence) {
      const start = bodyStart + m.index;
      const end = start + m[0].length;
      return text.slice(0, start) + replacement + text.slice(end);
    }
  }
  throw new Error(
    `occurrence ${occurrence} not found — body has fewer number tokens`,
  );
}

/**
 * Every dataset-derived figure's occurrence INDEX in the article body,
 * measured 2026-09-15 against the live it/id files — identical in both
 * languages, because the hourly translator reorders nothing, only rewords
 * (the whole reason position survives a reword the way sentence-regex
 * cannot for it/id). `numberTokenCount` is checked first in each locale's
 * describe block so a future structural change shows up as a clear count
 * mismatch, not a silently wrong value at every index below it.
 */
function positionalPins(
  c: ReturnType<typeof countFromCanonical>,
  b: ReturnType<typeof countBreakdown>,
  sep: string,
) {
  const pct = pctComma(c.pct);
  return [
    { index: 2, what: "methodology total", expected: group(c.total, sep) },
    { index: 5, what: "headline total", expected: group(c.total, sep) },
    {
      index: 6,
      what: "headline blocked count",
      expected: group(c.blocked, sep),
    },
    { index: 7, what: "headline percentage", expected: pct },
    {
      index: 9,
      what: "breakdown-intro count",
      expected: group(c.blocked, sep),
    },
    {
      index: 10,
      what: "risk-class category count",
      expected: group(b.riskClass, sep),
    },
    {
      index: 11,
      what: "moratorium category count",
      expected: group(b.moratorium, sep),
    },
    {
      index: 12,
      what: "closed-activity (TERTUTUP) category count",
      expected: group(b.tertutup, sep),
    },
    {
      index: 13,
      what: "TERTUTUP 0%-foreign-ownership sub-count",
      expected: group(b.tertutupZero, sep),
    },
    {
      index: 15,
      what: "TERTUTUP trap (100%-catalogue) sub-count",
      expected: group(b.tertutupNonZero, sep),
    },
    {
      index: 23,
      what: "non-classifiable category count",
      expected: group(b.nonClassificabile, sep),
    },
    {
      index: 24,
      what: "reserved-for-cooperatives category count",
      expected: group(b.pmaNoBesar, sep),
    },
    {
      index: 29,
      what: "remainder category count",
      expected: group(b.smallRemainder, sep),
    },
    {
      index: 30,
      what: "remainder: sector-regulator sub-count",
      expected: group(b.regolatoreSettoriale, sep),
    },
    {
      index: 31,
      what: "remainder: scope-dependent sub-count",
      expected: group(b.dipendeScopeBlockedTrue, sep),
    },
    {
      index: 32,
      what: "remainder: Bali-announced-closures sub-count",
      expected: group(b.baliClosuresSum, sep),
    },
    {
      index: 39,
      what: "correction-paragraph total",
      expected: group(c.total, sep),
    },
    {
      index: 40,
      what: "narrative percentage (945/39% correction paragraph)",
      expected: pct,
    },
    {
      index: 41,
      what: "closing-ratio blocked count",
      expected: group(c.blocked, sep),
    },
    { index: 42, what: "closing-ratio total", expected: group(c.total, sep) },
    { index: 43, what: "closing-ratio percentage", expected: pct },
    { index: 46, what: "not-blocked count", expected: group(c.open, sep) },
    {
      index: 47,
      what: "scope-dependent count among not-blocked codes",
      expected: group(b.scopeDependentNotBlocked, sep),
    },
    { index: 48, what: "closing count", expected: group(c.blocked, sep) },
  ];
}

describe("KBLI prose pins — published aggregates agree with the canonical", () => {
  it("fails loudly if an input is missing, instead of passing blind", () => {
    // W102: a gate whose input vanished must accuse itself, not report all-clear.
    expect(fs.existsSync(CANONICAL), `gate input missing: ${CANONICAL}`).toBe(
      true,
    );
    for (const { file } of ARTICLE_FILES) {
      const f = path.join(ARTICLE_DIR, file);
      expect(fs.existsSync(f), `gate input missing: ${f}`).toBe(true);
    }
  });

  it("the counts are internally coherent before anything is asserted about prose", () => {
    const { total, blocked, open } = countFromCanonical();
    expect(total).toBeGreaterThan(0);
    expect(blocked + open, "blocked + open must exhaust the dataset").toBe(
      total,
    );
  });

  it("the risk-class not-nationally-open sub-count is small enough to spell out in prose", () => {
    const b = countBreakdown();
    expect(
      b.riskClassNotNationallyOpen,
      `computed ${b.riskClassNotNationallyOpen} but SMALL_NUMBER_WORDS only covers 0-${
        SMALL_NUMBER_WORDS.length - 1
      } — extend the table or switch the "all but <word>" claim to a digit`,
    ).toBeLessThan(SMALL_NUMBER_WORDS.length);
  });

  describe(`${ARTICLE_BASE} [en]`, () => {
    const c = countFromCanonical();
    const b = countBreakdown();
    const EN_ANCHORS = [
      {
        what: "headline blocked count",
        re: /Of ([\d,]+) classified KBLI codes, ([\d,]+) are blocked/,
        expect: [group(c.total, ","), group(c.blocked, ",")],
      },
      {
        what: "headline percentage",
        re: /That is ([\d.]+)% — almost exactly one in three\./,
        expect: [c.pct.toFixed(1)],
      },
      {
        what: "methodology total",
        re: /The dataset holds \*\*([\d,]+) classified codes\*\*/,
        expect: [group(c.total, ",")],
      },
      {
        what: "breakdown-intro count",
        re: /those (\d+) break down into/,
        expect: [String(c.blocked)],
      },
      {
        what: "not-blocked count",
        re: /\(([\d,]+) codes carry no blocked flag/,
        expect: [group(c.open, ",")],
      },
      {
        what: "closing count",
        re: /backed by ([\d,]+) counted codes/,
        expect: [group(c.blocked, ",")],
      },
      {
        what: "ratio",
        re: /\*\*([\d,]+) of ([\d,]+) — ([\d.]+)%\*\*/,
        expect: [group(c.blocked, ","), group(c.total, ","), c.pct.toFixed(1)],
      },
      {
        what: "risk-class category count",
        re: /\*\*(\d+) — blocked by risk class\*\*/,
        expect: [String(b.riskClass)],
      },
      {
        what: "risk-class not-nationally-open sub-count (spelled out)",
        re: /all but (\w+) nationally open/,
        expect: [
          SMALL_NUMBER_WORDS[b.riskClassNotNationallyOpen] ??
            String(b.riskClassNotNationallyOpen),
        ],
      },
      {
        what: "moratorium category count",
        re: /\*\*(\d+) — blocked by the moratorium on other grounds\*\*/,
        expect: [String(b.moratorium)],
      },
      {
        what: "closed-activity category count",
        re: /\*\*(\d+) — closed on the activity itself\*\*/,
        expect: [String(b.tertutup)],
      },
      {
        what: "TERTUTUP 0%-foreign-ownership sub-count",
        re: /(\d+) of them carry 0% foreign ownership/,
        expect: [String(b.tertutupZero)],
      },
      {
        what: "TERTUTUP trap (100%-catalogue) sub-count",
        re: /The other (\d+) are the trap/,
        expect: [String(b.tertutupNonZero)],
      },
      {
        what: "non-classifiable category count",
        re: /\*\*(\d+) — no Bali position can be stated\*\*/,
        expect: [String(b.nonClassificabile)],
      },
      {
        what: "reserved-for-cooperatives category count",
        re: /\*\*(\d+) — reserved for cooperatives and MSMEs\*\*/,
        expect: [String(b.pmaNoBesar)],
      },
      {
        what: "remainder category count",
        re: /\*\*(\d+) — the remainder\*\*/,
        expect: [String(b.smallRemainder)],
      },
      {
        what: "remainder: sector-regulator sub-count",
        re: /(\d+) closed by their own sector regulator/,
        expect: [String(b.regolatoreSettoriale)],
      },
      {
        what: "remainder: scope-dependent sub-count",
        re: /(\d+) scope-dependent,/,
        expect: [String(b.dipendeScopeBlockedTrue)],
      },
      {
        what: "remainder: Bali-announced-closures sub-count",
        re: /(\d+) under Bali's own announced closures/,
        expect: [String(b.baliClosuresSum)],
      },
      {
        what: "narrative percentage (945/39% correction paragraph)",
        re: /the rate settles at \*\*([\d.]+)%\.\*\*/,
        expect: [c.pct.toFixed(1)],
      },
      {
        what: "scope-dependent count among not-blocked codes",
        re: /though (\d+) of them are scope-dependent/,
        expect: [String(b.scopeDependentNotBlocked)],
      },
    ];

    for (const probe of EN_ANCHORS) {
      it(`${probe.what} reproduces from the dataset`, () => {
        const text = fs.readFileSync(
          path.join(ARTICLE_DIR, `${ARTICLE_BASE}.mdx`),
          "utf-8",
        );
        const match = text.match(probe.re);
        expect(
          match,
          `anchor sentence not found in ${ARTICLE_BASE}.mdx — it was reworded; re-anchor this probe (${probe.re})`,
        ).not.toBeNull();
        expect(match!.slice(1)).toEqual(probe.expect);
      });
    }
  });

  for (const lang of ["it", "id"] as const) {
    const file = `${ARTICLE_BASE}.${lang}.mdx`;
    describe(`${ARTICLE_BASE} [${lang}]`, () => {
      const c = countFromCanonical();
      const b = countBreakdown();

      it("the body carries at least as many number tokens as the positional map expects", () => {
        const text = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
        const n = numberTokenCount(text);
        expect(
          n,
          `${file} body has ${n} number tokens — every positional pin below index ${n} is now reading a shifted occurrence; re-measure the map`,
        ).toBeGreaterThanOrEqual(48);
      });

      for (const pin of positionalPins(c, b, ".")) {
        it(`${pin.what} reproduces from the dataset`, () => {
          const text = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
          const actual = nthNumberToken(text, pin.index);
          expect(
            actual,
            `occurrence #${pin.index} (${pin.what}) in ${file} — expected "${pin.expected}"`,
          ).toBe(pin.expected);
        });
      }
    });
  }

  it("no superseded reading of this dataset survives in any language", () => {
    // The specific figures this article retracted in public. They are listed by
    // the SENTENCE that would carry them, so the historical mention inside the
    // article's own correction section ("we brought a working number of ~945
    // codes, ~39% blocked") stays legal — quoting a figure in order to retract
    // it is the cure, not the disease.
    const SUPERSEDED = [
      "465 counted codes",
      "465 codici contati",
      "465 kode yang dihitung",
      "1,094 codes survive",
      "1.094 codici sopravvissuti",
      "1.094 kode bertahan",
      "465 of 1,559",
      "465 su 1.559",
      "465 dari 1.559",
      // Retracted 2026-08-12 by the Codex adversarial review: the 1,041 are the
      // codes that carry no blocked flag, NOT codes that "survive" — 70 of them
      // are scope-dependent and a handful unclassified, so the survival reading
      // over-promises. The locution is banned in every language, at any number.
      "codes survive",
      "codici sopravvissuti",
      "kode bertahan",
    ];
    for (const { file } of ARTICLE_FILES) {
      const text = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
      for (const dead of SUPERSEDED) {
        expect(
          text.includes(dead),
          `${file} reasserts the superseded "${dead}"`,
        ).toBe(false);
      }
    }
  });

  it("the six published category counts sum to the blocked total the headline states", () => {
    // On 2026-06-23 the article's category list (372+48+68+17+7+6 = 518) fell
    // one short of its own 519 headline — a reader who adds up the "kinds of
    // no" gets a different number than the "how many are blocked" sentence.
    // Both sides here are recomputed from the canonical, never hard-coded: if
    // a future cure adds/removes a status this breaks until the article's
    // breakdown is updated to cover it (or the "remainder" category widens).
    const { blocked } = countFromCanonical();
    const b = countBreakdown();
    const sum =
      b.riskClass +
      b.moratorium +
      b.tertutup +
      b.nonClassificabile +
      b.pmaNoBesar +
      b.smallRemainder;
    expect(
      sum,
      `category breakdown (${sum}) must sum to the blocked total (${blocked}) — a new l4_bali.status among blocked rows would go unreported`,
    ).toBe(blocked);
  });

  // ---------------------------------------------------------------------
  // GUILT — reproduces the Codex GPT-5.6-sol xhigh adversarial review's two
  // demonstrated mutations (2026-09-15, BLOCKER finding 1) against the NEW
  // positional mechanism, and proves each one is now caught.
  // ---------------------------------------------------------------------
  describe("positional number-matching resists the Codex adversarial review's reproductions (2026-09-15)", () => {
    it("[en] a superstring mutation is rejected — \\d+ captures the WHOLE run, not a substring", () => {
      const mutated = fs
        .readFileSync(path.join(ARTICLE_DIR, `${ARTICLE_BASE}.mdx`), "utf-8")
        .replace(
          "**373 — blocked by risk class**",
          "**1373 — blocked by risk class**",
        );
      const match = mutated.match(/\*\*(\d+) — blocked by risk class\*\*/);
      expect(match?.[1]).toBe("1373");
      expect(match?.[1]).not.toBe(String(countBreakdown().riskClass));
    });

    for (const lang of ["it", "id"] as const) {
      const file = `${ARTICLE_BASE}.${lang}.mdx`;

      it(`[${lang}] a superstring mutation (373→1373 style, every category count) is rejected at each occurrence`, () => {
        // Reproduces the review's first demonstration: prefixing every
        // category count with "1" (373→1373, 48→148, 68→168, 17→117, 7→17,
        // 6→16) used to leave the old substring-based window probe green.
        // Splice from the LAST index to the first so earlier occurrence
        // indices stay valid as the string shifts.
        const live = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
        let mutated = live;
        mutated = spliceNumberAt(mutated, 29, "16"); // remainder 6 -> 16
        mutated = spliceNumberAt(mutated, 24, "17"); // pmaNoBesar 7 -> 17
        mutated = spliceNumberAt(mutated, 23, "117"); // nonClassificabile 17 -> 117
        mutated = spliceNumberAt(mutated, 12, "168"); // tertutup 68 -> 168
        mutated = spliceNumberAt(mutated, 11, "148"); // moratorium 48 -> 148
        mutated = spliceNumberAt(mutated, 10, "1373"); // riskClass 373 -> 1373

        const b = countBreakdown();
        expect(nthNumberToken(mutated, 10)).toBe("1373");
        expect(nthNumberToken(mutated, 10)).not.toBe(String(b.riskClass));
        expect(nthNumberToken(mutated, 11)).not.toBe(String(b.moratorium));
        expect(nthNumberToken(mutated, 12)).not.toBe(String(b.tertutup));
        expect(nthNumberToken(mutated, 23)).not.toBe(
          String(b.nonClassificabile),
        );
        expect(nthNumberToken(mutated, 24)).not.toBe(String(b.pmaNoBesar));
        expect(nthNumberToken(mutated, 29)).not.toBe(String(b.smallRemainder));
      });

      it(`[${lang}] a wrong-paragraph mutation (headline/correction/closing) is caught at its OWN occurrence even though an untouched correct mention survives elsewhere`, () => {
        // Reproduces the review's second demonstration: headline blocked,
        // correction-paragraph percentage, and closing count all wrong at
        // once — while the breakdown-intro (occurrence 9) and the
        // closing-ratio (occurrence 41) mentions are DELIBERATELY left
        // untouched, the "untouched correct mention survives elsewhere" half
        // of the reproduction.
        //
        // 2026-09-15 SAETTA-20260915 W-H PR-2b (93114/43110 restore, D5f):
        // the census moved 519->518 / 33.3%->33.2%, so the review's original
        // injected "wrong" values (518 / 33,2) are now the CORRECT ones —
        // reusing them here would make this guilt test assert '518' !== '518'
        // regardless of any real mutation. Injected values below are wrong
        // under the current AND the pre-2026-09-15 census on purpose, so a
        // future correction to this same figure cannot silently reopen this
        // gap again.
        const live = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
        let mutated = live;
        mutated = spliceNumberAt(mutated, 48, "509"); // closing count
        mutated = spliceNumberAt(mutated, 40, "33,9"); // narrative percentage
        mutated = spliceNumberAt(mutated, 6, "509"); // headline blocked

        const c = countFromCanonical();
        // The untouched siblings genuinely still read correctly:
        expect(nthNumberToken(mutated, 9)).toBe(String(c.blocked));
        expect(nthNumberToken(mutated, 41)).toBe(String(c.blocked));
        // But each MUTATED occurrence is caught at its OWN index — the
        // mechanism never falls back to "some other correct mention exists":
        expect(nthNumberToken(mutated, 48)).not.toBe(group(c.blocked, "."));
        expect(nthNumberToken(mutated, 40)).not.toBe(pctComma(c.pct));
        expect(nthNumberToken(mutated, 6)).not.toBe(group(c.blocked, "."));
      });
    }
  });
});

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
// hard-coded, or the gate would only pin the article to a past reading. The
// exceptions are literal HISTORY: figures the article quotes as "what we used
// to say" (518 / 33.2% / 945 / 39%) are frozen prose, correctly independent of
// the live canonical — they describe a past reading, not the current one — so
// they are deliberately left unpinned here, exactly as the superseded 945/39%
// figure was in the previous revision of this article and this gate.
//
// EN IS SENTENCE-REGEX; IT/ID ARE POSITIONAL. The hourly translator rewords the
// it/id articles on every run, so a probe anchored to exact wording turns into
// a treadmill a fresh reword keeps breaking; EN stays sentence-regex because it
// is the human-authored source, never re-translated.
//
// POSITIONAL MATCHING (it/id): every number token in the article body
// (frontmatter excluded) is extracted once, in reading order, as a maximal
// digit run ("1.041" is one token, never "1" + "041" — so "41" can never match
// inside it), and each claim is pinned to the token's OCCURRENCE INDEX,
// verified against the live it/id files (`numberTokens()` dump, 2026-09-15,
// W-J B1 v2 redo, post-#6596) and IDENTICAL in both languages because the
// translator reorders nothing, only rewords. A wrong-paragraph swap cannot
// hide behind a correct sibling occurrence, because each pin reads its own
// index and nothing else's.
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
  l4_bali?: { blocked?: boolean; status?: string; confidence?: string };
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
 * The published "the-honest-map" article (rewritten 2026-09-15, W-J B1 v2
 * redo, after the applied-closure overlay narrowed `blocked` from ~518 to
 * 131 on the post-#6596 canonical) breaks its headline down into FIVE
 * category counts, plus a separate "needs verifying" count and a "no flag at
 * all" count. This recomputes every one of them so the prose can be pinned
 * to the ACTUAL per-status breakdown, not a copy that drifts the moment a
 * cure changes one status.
 */
function countBreakdown() {
  const raw = JSON.parse(fs.readFileSync(CANONICAL, "utf-8")) as {
    data: Row[];
  };
  const rows = raw.data;
  const blockedRows = rows.filter((r) => r.l4_bali?.blocked === true);
  const byStatus = (status: string) =>
    blockedRows.filter((r) => r.l4_bali?.status === status);

  const tertutupRows = byStatus("TERTUTUP");
  const tertutup = tertutupRows.length;
  // Restored 2026-09-15 (cure round finding 2): "closed nationally" is not a
  // uniform 0%-cap population. A TERTUPUP l4_bali status can also come from a
  // separate national law reserving the ACTIVITY (not the ownership share) —
  // pma_status/pma_max_asing on those records still reads TERBUKA/100. Split
  // so the prose can say which is which instead of a blanket "0% foreign
  // ownership" that is false for the second group.
  // Exact values, not "zero vs non-zero" (Codex sol cure verification): the
  // prose says "66 at 0%" and "6 show 100%", so a record drifting 100 -> 49
  // must move a pin, and an absent cap must count as neither.
  const tertutupZero = tertutupRows.filter((r) => r.pma_max_asing === 0).length;
  const tertutupNonZero = tertutupRows.filter(
    (r) => r.pma_max_asing === 100,
  ).length;
  const chiusoBali = byStatus("CHIUSO_BALI").length;
  // "14 — held pending verification": every blocked status this compiler does
  // not yet stand fully behind at the individual-code level.
  const heldPending =
    byStatus("CHIUSO_MORATORIA_BALI").length +
    byStatus("BLOCCATO_DIPENDE_SCOPE").length +
    byStatus("CHIUSO_BALI_PROPOSTO").length;
  const pmaNoBesar = byStatus("CHIUSO_PMA_NO_BESAR").length;
  const regolatoreSettoriale = byStatus("CHIUSO_REGOLATORE_SETTORIALE").length;

  const attenzione = rows.filter(
    (r) =>
      r.l4_bali?.status === "ATTENZIONE_FASCIA_BALI" &&
      r.l4_bali?.blocked === false,
  ).length;

  const { total, blocked } = countFromCanonical();
  const openNoFlag = total - blocked - attenzione;

  const scopeDependentNotBlocked = rows.filter(
    (r) =>
      r.l4_bali?.status === "BLOCCATO_DIPENDE_SCOPE" &&
      r.l4_bali?.blocked === false,
  ).length;
  const nonClassificabileNotBlocked = rows.filter(
    (r) =>
      r.l4_bali?.status === "NON_CLASSIFICABILE" &&
      r.l4_bali?.blocked === false,
  ).length;

  // Added 2026-09-15 (cure round finding 3): "135 closed, full stop" hid that
  // 29 of them rest on a conservative reading Bali Zero applied itself
  // (verdict_state=provisional at the record level), not a citation naming
  // the exact code. Recomputed from `l4_bali.confidence` — HIGH is the
  // confirmed half — so this pin drifts the instant the compiler changes any
  // record's confidence, exactly like every other figure in this file.
  const highConfidenceBlocked = blockedRows.filter(
    (r) => r.l4_bali?.confidence === "HIGH",
  ).length;
  const conservativeBlocked = blockedRows.length - highConfidenceBlocked;
  const conservativeOf = (rows: Row[]) =>
    rows.filter((r) => r.l4_bali?.confidence !== "HIGH").length;
  const chiusoBaliConservative = conservativeOf(byStatus("CHIUSO_BALI"));
  const tertutupConservative = conservativeOf(tertutupRows);
  const heldPendingConservative =
    conservativeBlocked - chiusoBaliConservative - tertutupConservative;

  return {
    tertutup,
    tertutupZero,
    tertutupNonZero,
    chiusoBali,
    heldPending,
    pmaNoBesar,
    regolatoreSettoriale,
    attenzione,
    openNoFlag,
    scopeDependentNotBlocked,
    nonClassificabileNotBlocked,
    highConfidenceBlocked,
    conservativeBlocked,
    chiusoBaliConservative,
    tertutupConservative,
    heldPendingConservative,
  };
}

/** `1041` → `1,041` (en) / `1.041` (it, id). */
const group = (n: number, sep: string) =>
  n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, sep);

/** `8.4` → `8,4` — the IT/ID decimal-comma reading of a percentage that is
 * always computed as a plain `X.Y` number (see `countFromCanonical().pct`). */
const pctComma = (pct: number) => pct.toFixed(1).replace(".", ",");

// -----------------------------------------------------------------------
// POSITIONAL NUMBER MATCHING (it/id) — see the file header.
// -----------------------------------------------------------------------

/** A maximal run of digits, optionally with internal `.`/`,` separators —
 * "1.041" is ONE token, never "1" + "041" — so an expected "41" never matches
 * inside an actual "1041". Equality against an expected formatted number is
 * always on the WHOLE token. */
const NUMBER_TOKEN_SOURCE = String.raw`\d(?:[\d.,]*\d)?`;

/** Everything after the frontmatter's closing `---` delimiter. Frontmatter
 * carries its own numbers (`publishedAt`, `updatedAt`, `readingTime`,
 * `aiConfidenceScore`) that are not prose and must never be counted as an
 * "occurrence". */
function articleBody(text: string): string {
  const first = text.indexOf("---");
  if (first === -1) return text;
  const second = text.indexOf("---", first + 3);
  if (second === -1) return text;
  return text.slice(second + 3);
}

/** The `n`th (1-indexed) number token in `text`'s BODY, in reading order, or
 * `null` if the body has fewer than `n`. This is POSITION, not a value
 * search: two genuine mentions of the same figure are different occurrences,
 * and a pin on one index is blind to what happens at another. */
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
 * SAME figure — untouched. */
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
 * re-measured 2026-09-15 (cure round, findings 2+3: the TERTUTUP zero/
 * non-zero split and the confirmed/conservative confidence split added two
 * new sentences, shifting every later index) against the live it/id files —
 * identical in both languages, because the translator reorders nothing, only
 * rewords. Indices NOT listed here (dates, code citations like 55101-55106
 * or 01111/47112/69102/69104/86201/86202, the "18 business fields" citation,
 * the frozen 518/33.2%/945/39% history) are deliberately unpinned — see file
 * header. `numberTokenCount` is checked first in each locale's describe
 * block so a future structural change shows up as a clear count mismatch.
 */
function positionalPins(
  c: ReturnType<typeof countFromCanonical>,
  b: ReturnType<typeof countBreakdown>,
  sep: string,
) {
  const pct = pctComma(c.pct);
  return [
    { index: 2, what: "method total", expected: group(c.total, sep) },
    { index: 4, what: "headline total", expected: group(c.total, sep) },
    {
      index: 5,
      what: "headline blocked count",
      expected: group(c.blocked, sep),
    },
    { index: 6, what: "headline percentage", expected: pct },
    {
      index: 7,
      what: "breakdown-intro count",
      expected: group(c.blocked, sep),
    },
    {
      index: 8,
      what: "TERTUTUP category count",
      expected: group(b.tertutup, sep),
    },
    {
      index: 9,
      what: "TERTUTUP zero-cap sub-count",
      expected: group(b.tertutupZero, sep),
    },
    {
      index: 11,
      what: "TERTUTUP non-zero-cap sub-count",
      expected: group(b.tertutupNonZero, sep),
    },
    {
      index: 25,
      what: "CHIUSO_BALI category count",
      expected: group(b.chiusoBali, sep),
    },
    {
      index: 33,
      what: 'CHIUSO_BALI restated ("land on N codes")',
      expected: group(b.chiusoBali, sep),
    },
    {
      index: 39,
      what: "held-pending-verification category count",
      expected: group(b.heldPending, sep),
    },
    {
      index: 40,
      what: "reserved-for-cooperatives category count",
      expected: group(b.pmaNoBesar, sep),
    },
    {
      index: 45,
      what: "sector-regulator category count",
      expected: group(b.regolatoreSettoriale, sep),
    },
    {
      index: 46,
      what: "arithmetic sentence: blocked total",
      expected: group(c.blocked, sep),
    },
    {
      index: 47,
      what: "arithmetic sentence: TERTUTUP",
      expected: group(b.tertutup, sep),
    },
    {
      index: 48,
      what: "arithmetic sentence: CHIUSO_BALI",
      expected: group(b.chiusoBali, sep),
    },
    {
      index: 49,
      what: "arithmetic sentence: held-pending",
      expected: group(b.heldPending, sep),
    },
    {
      index: 50,
      what: "arithmetic sentence: reserved-for-cooperatives",
      expected: group(b.pmaNoBesar, sep),
    },
    {
      index: 51,
      what: "arithmetic sentence: sector-regulator",
      expected: group(b.regolatoreSettoriale, sep),
    },
    {
      index: 52,
      what: "confidence split intro total",
      expected: group(c.blocked, sep),
    },
    {
      index: 53,
      what: "confidence split: HIGH-confidence sub-count",
      expected: group(b.highConfidenceBlocked, sep),
    },
    {
      index: 54,
      what: "confidence split: conservative-reading sub-count",
      expected: group(b.conservativeBlocked, sep),
    },
    {
      index: 55,
      what: "conservative split: CHIUSO_BALI share",
      expected: group(b.chiusoBaliConservative, sep),
    },
    {
      index: 56,
      what: "conservative split: CHIUSO_BALI total restated",
      expected: group(b.chiusoBali, sep),
    },
    {
      index: 60,
      what: "conservative split: held-pending share",
      expected: group(b.heldPendingConservative, sep),
    },
    {
      index: 61,
      what: "conservative split: held-pending total restated",
      expected: group(b.heldPending, sep),
    },
    {
      index: 62,
      what: "conservative split: TERTUTUP share",
      expected: group(b.tertutupConservative, sep),
    },
    {
      index: 63,
      what: "conservative-reading sub-count restated",
      expected: group(b.conservativeBlocked, sep),
    },
    {
      index: 64,
      what: "ATTENZIONE_FASCIA_BALI count",
      expected: group(b.attenzione, sep),
    },
    {
      index: 67,
      what: "ATTENZIONE_FASCIA_BALI restated",
      expected: group(b.attenzione, sep),
    },
    {
      index: 74,
      what: "correction paragraph: new count",
      expected: group(c.blocked, sep),
    },
    {
      index: 78,
      what: "closing reading: blocked count",
      expected: group(c.blocked, sep),
    },
    { index: 79, what: "closing reading: percentage", expected: pct },
    {
      index: 80,
      what: "closing reading: HIGH-confidence sub-count",
      expected: group(b.highConfidenceBlocked, sep),
    },
    {
      index: 81,
      what: "closing reading: conservative-reading sub-count",
      expected: group(b.conservativeBlocked, sep),
    },
    {
      index: 83,
      what: "closing reading: ATTENZIONE_FASCIA_BALI count",
      expected: group(b.attenzione, sep),
    },
    {
      index: 84,
      what: "closing reading: no-flag count",
      expected: group(b.openNoFlag, sep),
    },
    {
      index: 85,
      what: "closing reading: scope-dependent sub-count",
      expected: group(b.scopeDependentNotBlocked, sep),
    },
    {
      index: 86,
      what: "closing reading: unclassified sub-count",
      expected: group(b.nonClassificabileNotBlocked, sep),
    },
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
    const b = countBreakdown();
    expect(
      b.attenzione + b.openNoFlag,
      "ATTENZIONE + no-flag must exhaust the not-blocked population",
    ).toBe(open);
  });

  describe(`${ARTICLE_BASE} [en]`, () => {
    const c = countFromCanonical();
    const b = countBreakdown();
    const EN_ANCHORS = [
      {
        what: "method total",
        re: /The dataset holds \*\*([\d,]+) classified codes\*\*/,
        expect: [group(c.total, ",")],
      },
      {
        what: "headline (total, blocked, percentage)",
        re: /Of ([\d,]+) classified KBLI codes, ([\d,]+) are closed to a new PT PMA in Bali today\. That is ([\d.]+)%\./,
        expect: [group(c.total, ","), group(c.blocked, ","), c.pct.toFixed(1)],
      },
      {
        what: "breakdown-intro count",
        re: /make up that (\d+) —/,
        expect: [String(c.blocked)],
      },
      {
        what: "TERTUTUP category count",
        re: /\*\*(\d+) — closed by an ownership restriction on the activity itself\*\*/,
        expect: [String(b.tertutup)],
      },
      {
        what: "TERTUTUP zero-cap sub-count (restored 2026-09-15, finding 2)",
        re: /(\d+) of them carry 0% foreign ownership in the national catalogue outright/,
        expect: [String(b.tertutupZero)],
      },
      {
        what: "TERTUTUP non-zero-cap sub-count (restored 2026-09-15, finding 2)",
        re: /The other (\d+) show 100% in that same ownership field/,
        expect: [String(b.tertutupNonZero)],
      },
      {
        what: "CHIUSO_BALI category count",
        re: /\*\*(\d+) — closed by Bali itself\*\*/,
        expect: [String(b.chiusoBali)],
      },
      {
        what: 'CHIUSO_BALI restated ("land on N of today\'s codes")',
        re: /land on (\d+) of today's codes/,
        expect: [String(b.chiusoBali)],
      },
      {
        what: "held-pending-verification category count",
        re: /\*\*(\d+) — held pending verification\*\*/,
        expect: [String(b.heldPending)],
      },
      {
        what: "reserved-for-cooperatives category count",
        re: /\*\*(\d+) — reserved for cooperatives and MSMEs\*\*/,
        expect: [String(b.pmaNoBesar)],
      },
      {
        what: "sector-regulator category count",
        re: /\*\*(\d+) — closed by their own sector regulator\*\*/,
        expect: [String(b.regolatoreSettoriale)],
      },
      {
        what: "arithmetic sentence (blocked = 5 categories)",
        re: /That is the whole (\d+): (\d+) \+ (\d+) \+ (\d+) \+ (\d+) \+ (\d+)\./,
        expect: [
          String(c.blocked),
          String(b.tertutup),
          String(b.chiusoBali),
          String(b.heldPending),
          String(b.pmaNoBesar),
          String(b.regolatoreSettoriale),
        ],
      },
      {
        what: "confidence split: HIGH-confidence sub-count (added 2026-09-15, finding 3)",
        re: /Not all \d+ rest on the same footing: (\d+) carry HIGH confidence in our data/,
        expect: [String(b.highConfidenceBlocked)],
      },
      {
        what: "confidence split: conservative-reading sub-count (added 2026-09-15, finding 3)",
        re: /The other (\d+) are a conservative reading we applied ourselves — (\d+) of the (\d+) "closed by Bali itself" codes,.*?; (\d+) of the (\d+) "held pending verification"; and (\d+) nationally closed code/,
        expect: [
          String(b.conservativeBlocked),
          String(b.chiusoBaliConservative),
          String(b.chiusoBali),
          String(b.heldPendingConservative),
          String(b.heldPending),
          String(b.tertutupConservative),
        ],
      },
      {
        what: "ATTENZIONE_FASCIA_BALI count",
        re: /A much larger group — \*\*(\d+) codes\*\* — carries a warning/,
        expect: [String(b.attenzione)],
      },
      {
        what: "ATTENZIONE_FASCIA_BALI restated",
        re: /These (\d+) codes sit in that gap/,
        expect: [String(b.attenzione)],
      },
      {
        what: "correction paragraph: honest count drops to N",
        re: /the honest count drops from 518 to (\d+)\./,
        expect: [String(c.blocked)],
      },
      {
        what: "closing reading: blocked count + percentage + confidence split (reworded 2026-09-15, finding 3 — dropped the absolute 'full stop' claim)",
        re: /\*\*(\d+) codes \(([\d.]+)%\) are blocked\*\* in our data — (\d+) at HIGH confidence, (\d+) on a conservative reading/,
        expect: [
          String(c.blocked),
          c.pct.toFixed(1),
          String(b.highConfidenceBlocked),
          String(b.conservativeBlocked),
        ],
      },
      {
        what: "closing reading: ATTENZIONE_FASCIA_BALI count",
        re: /\*\*(\d+) codes \(about a quarter\) need a live check\*\*/,
        expect: [String(b.attenzione)],
      },
      {
        what: "closing reading: no-flag + sub-counts",
        re: /\*\*([\d,]+) codes carry neither flag\*\* — though (\d+) of them are scope-dependent and (\d+) unclassified/,
        expect: [
          group(b.openNoFlag, ","),
          String(b.scopeDependentNotBlocked),
          String(b.nonClassificabileNotBlocked),
        ],
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

    it("still names 518 / 33.2% / 945 / 39% ONLY as retracted history, and never 13 May 2026", () => {
      const text = fs.readFileSync(
        path.join(ARTICLE_DIR, `${ARTICLE_BASE}.mdx`),
        "utf-8",
      );
      expect(text).toMatch(
        /Until 15 September 2026, this article counted \*\*518 codes, 33\.2% blocked\*\*/,
      );
      expect(text).toMatch(/"about 945 codes, roughly 39% blocked"/);
      expect(text).not.toMatch(/13 May 2026/);
      expect(text).not.toMatch(/13\/5\/26/);
    });
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
        ).toBeGreaterThanOrEqual(86);
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

      it("never asserts 13 May 2026 / 13/5/26", () => {
        const text = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
        expect(text).not.toMatch(/13 May 2026/);
        expect(text).not.toMatch(/13\/5\/26/);
      });
    });
  }

  it("no superseded reading of this dataset survives in any language", () => {
    // The specific figures this article has retracted in public, ever. They
    // are listed by the SENTENCE that would carry them, so the historical
    // mention inside the article's own correction sections (518/33.2%,
    // 945/39%) stays legal — quoting a figure in order to retract it is the
    // cure, not the disease.
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
      "codes survive",
      "codici sopravvissuti",
      "kode bertahan",
      // Retracted 2026-09-15 (W-J B1 v2 redo, post-#6596): the raw
      // risk-class-based ~518/33.2% headline that counted every
      // BLOCCATO_CLASSE_RISCHIO/moratorium-touched code as blocked, instead
      // of what Bali's applied closure actually covers, is now history, not
      // a live claim — banned everywhere EXCEPT the dated correction
      // sentence itself, which the anchor tests above pin explicitly.
      "Of 1,559 classified KBLI codes, 518 are",
      "Su 1.559 codici KBLI classificati, 518 sono bloccati",
      "Dari 1.559 kode KBLI yang diklasifikasikan, 518 diblokir",
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

  it("the five published category counts sum to the blocked total the headline states", () => {
    const { blocked } = countFromCanonical();
    const b = countBreakdown();
    const sum =
      b.tertutup +
      b.chiusoBali +
      b.heldPending +
      b.pmaNoBesar +
      b.regolatoreSettoriale;
    expect(
      sum,
      `category breakdown (${sum}) must sum to the blocked total (${blocked}) — a new l4_bali.status among blocked rows would go unreported`,
    ).toBe(blocked);
  });

  it("ATTENZIONE_FASCIA_BALI plus the no-flag count exhausts every not-blocked code", () => {
    const { open } = countFromCanonical();
    const b = countBreakdown();
    expect(b.attenzione + b.openNoFlag).toBe(open);
  });

  // ---------------------------------------------------------------------
  // GUILT — proves the positional mechanism catches (a) a superstring
  // mutation and (b) a wrong-occurrence mutation that leaves an untouched,
  // genuinely-correct sibling occurrence of the SAME figure elsewhere.
  // ---------------------------------------------------------------------
  describe("positional number-matching catches a wrong-paragraph or superstring mutation", () => {
    it("[en] a superstring mutation is rejected — \\d+ captures the WHOLE run, not a substring", () => {
      const mutated = fs
        .readFileSync(path.join(ARTICLE_DIR, `${ARTICLE_BASE}.mdx`), "utf-8")
        .replace(
          "**72 — closed by an ownership restriction",
          "**172 — closed by an ownership restriction",
        );
      const match = mutated.match(
        /\*\*(\d+) — closed by an ownership restriction on the activity itself\*\*/,
      );
      expect(match?.[1]).toBe("172");
      expect(match?.[1]).not.toBe(String(countBreakdown().tertutup));
    });

    for (const lang of ["it", "id"] as const) {
      const file = `${ARTICLE_BASE}.${lang}.mdx`;

      it(`[${lang}] a superstring mutation on every category count is rejected at each occurrence`, () => {
        const live = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
        let mutated = live;
        // Splice from the LAST index to the first so earlier indices stay
        // valid. Indices re-measured 2026-09-15 (cure round, findings 2+3):
        // the TERTUTUP zero/non-zero split and confidence split each added a
        // sentence, shifting every category count's occurrence later.
        mutated = spliceNumberAt(mutated, 45, "12"); // regolatoreSettoriale 2 -> 12
        mutated = spliceNumberAt(mutated, 40, "17"); // pmaNoBesar 7 -> 17
        mutated = spliceNumberAt(mutated, 39, "114"); // heldPending 14 -> 114
        mutated = spliceNumberAt(mutated, 25, "140"); // chiusoBali 40 -> 140
        mutated = spliceNumberAt(mutated, 8, "172"); // tertutup 72 -> 172

        const b = countBreakdown();
        expect(nthNumberToken(mutated, 8)).toBe("172");
        expect(nthNumberToken(mutated, 8)).not.toBe(String(b.tertutup));
        expect(nthNumberToken(mutated, 25)).toBe("140");
        expect(nthNumberToken(mutated, 25)).not.toBe(String(b.chiusoBali));
        expect(nthNumberToken(mutated, 39)).toBe("114");
        expect(nthNumberToken(mutated, 39)).not.toBe(String(b.heldPending));
        expect(nthNumberToken(mutated, 40)).toBe("17");
        expect(nthNumberToken(mutated, 40)).not.toBe(String(b.pmaNoBesar));
        expect(nthNumberToken(mutated, 45)).toBe("12");
        expect(nthNumberToken(mutated, 45)).not.toBe(
          String(b.regolatoreSettoriale),
        );
      });

      it(`[${lang}] a wrong-paragraph mutation (headline vs. closing reading) is caught at its OWN occurrence even though an untouched correct mention survives elsewhere`, () => {
        // Mutate ONLY the headline blocked count (index 5) and the closing
        // percentage (index 79) — deliberately leaving the arithmetic
        // sentence's blocked count (index 46) and the correction paragraph's
        // (index 74) untouched, so a "search anywhere, accept any match"
        // design would hide the mutation behind those correct siblings.
        // Indices re-measured 2026-09-15 (cure round, findings 2+3).
        const live = fs.readFileSync(path.join(ARTICLE_DIR, file), "utf-8");
        let mutated = live;
        mutated = spliceNumberAt(mutated, 79, "9,1"); // closing percentage
        mutated = spliceNumberAt(mutated, 5, "999"); // headline blocked count

        const c = countFromCanonical();
        const pct = pctComma(c.pct);
        // The untouched siblings genuinely still read correctly:
        expect(nthNumberToken(mutated, 46)).toBe(String(c.blocked));
        expect(nthNumberToken(mutated, 74)).toBe(String(c.blocked));
        // But each MUTATED occurrence is caught at its OWN index:
        expect(nthNumberToken(mutated, 5)).not.toBe(group(c.blocked, "."));
        expect(nthNumberToken(mutated, 79)).toBe("9,1");
        expect(nthNumberToken(mutated, 79)).not.toBe(pct);
      });
    }
  });
});

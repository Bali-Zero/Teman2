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
// IT/ID PROBES ARE NUMBER-WINDOW, NOT SENTENCE-REGEX (2026-09-13). The hourly
// translator rewords the it/id articles on every run, and a probe anchored to
// exact wording ("codici senza flag di blocco" → "codici non riportano il
// flag bloccato" → "codici non portano il flag bloccato" …) turns into a
// treadmill of alternations that a fresh reword breaks again. The EN probes
// stay sentence-regex (EN is the human-authored source, not re-translated
// hourly). For it/id, each claim instead asserts that its expected numbers —
// still recomputed from the canonical, never hard-coded — appear in the file
// IN ORDER within a WINDOW of characters of each other, which survives any
// synonym/word-order reword but still catches a wrong or invented figure.
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

type Row = { l4_bali?: { blocked?: boolean } };

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

/** `1041` → `1,041` (en) / `1.041` (it, id). */
const group = (n: number, sep: string) =>
  n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, sep);

/** How many characters after one expected number the next one must land
 * within, for the it/id number-window probes to count them as "the same
 * claim" rather than two unrelated mentions of the same figure. */
const NUMBER_WINDOW = 400;

/**
 * Does `numbers` occur, in that ORDER, somewhere in `text`, each subsequent
 * one within `window` chars of the end of the previous one? Tries every
 * occurrence of the first number as a starting point (a figure like "1.559"
 * legitimately repeats across a translated article — e.g. once in the
 * methodology paragraph, once in the headline), so it succeeds as soon as ONE
 * window carries the whole sequence in order — which is what "the sentence
 * still makes this claim, however it's worded" means for a prose pin.
 */
function numbersInOrderWithinWindow(
  text: string,
  numbers: string[],
  window = NUMBER_WINDOW,
): boolean {
  if (numbers.length === 0) return true;
  const [first, ...rest] = numbers;
  let from = 0;
  for (;;) {
    const start = text.indexOf(first, from);
    if (start === -1) return false;
    let cursor = start + first.length;
    let ok = true;
    for (const n of rest) {
      const idx = text.indexOf(n, cursor);
      if (idx === -1 || idx > cursor + window) {
        ok = false;
        break;
      }
      cursor = idx + n.length;
    }
    if (ok) return true;
    from = start + 1;
  }
}

describe("KBLI prose pins — published aggregates agree with the canonical", () => {
  it("fails loudly if an input is missing, instead of passing blind", () => {
    // W102: a gate whose input vanished must accuse itself, not report all-clear.
    expect(fs.existsSync(CANONICAL), `gate input missing: ${CANONICAL}`).toBe(
      true,
    );
    for (const suffix of ["", ".it", ".id"]) {
      const f = path.join(ARTICLE_DIR, `${ARTICLE_BASE}${suffix}.mdx`);
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

  /**
   * Each entry anchors ONE sentence in ONE language to ONE recomputed value.
   * The anchor is the surrounding words, so the assertion cannot drift onto a
   * different number that happens to share the digits.
   */
  const CLAIMS = [
    {
      lang: "en",
      file: `${ARTICLE_BASE}.mdx`,
      sep: ",",
      anchors: (c: ReturnType<typeof countFromCanonical>) => [
        {
          what: "headline blocked count",
          re: /Of ([\d,]+) classified KBLI codes, ([\d,]+) are blocked/,
          expect: [group(c.total, ","), group(c.blocked, ",")],
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
          expect: [
            group(c.blocked, ","),
            group(c.total, ","),
            c.pct.toFixed(1),
          ],
        },
      ],
    },
    {
      lang: "it",
      file: `${ARTICLE_BASE}.it.mdx`,
      sep: ".",
      anchors: (c: ReturnType<typeof countFromCanonical>) => [
        {
          what: "headline blocked count",
          numbers: [group(c.total, "."), group(c.blocked, ".")],
        },
        {
          what: "not-blocked count",
          numbers: [group(c.open, ".")],
        },
        {
          what: "closing count",
          numbers: [group(c.blocked, ".")],
        },
      ],
    },
    {
      lang: "id",
      file: `${ARTICLE_BASE}.id.mdx`,
      sep: ".",
      anchors: (c: ReturnType<typeof countFromCanonical>) => [
        {
          what: "headline blocked count",
          numbers: [group(c.total, "."), group(c.blocked, ".")],
        },
        {
          what: "not-blocked count",
          numbers: [group(c.open, ".")],
        },
        {
          what: "closing count",
          numbers: [group(c.blocked, ".")],
        },
      ],
    },
  ];

  for (const claim of CLAIMS) {
    describe(`${ARTICLE_BASE} [${claim.lang}]`, () => {
      for (const probe of claim.anchors(countFromCanonical())) {
        it(`${probe.what} reproduces from the dataset`, () => {
          const text = fs.readFileSync(
            path.join(ARTICLE_DIR, claim.file),
            "utf-8",
          );
          if ("re" in probe) {
            // EN: sentence-regex. EN is human-authored, not re-translated
            // hourly, so a reword here is a real content change worth
            // re-anchoring by hand.
            const match = text.match(probe.re);
            expect(
              match,
              `anchor sentence not found in ${claim.file} — it was reworded; re-anchor this probe (${probe.re})`,
            ).not.toBeNull();
            expect(match!.slice(1)).toEqual(probe.expect);
          } else {
            // it/id: number-window. Survives a translator reword; still
            // fails if the expected figure(s) are missing or out of order.
            const ok = numbersInOrderWithinWindow(text, probe.numbers);
            expect(
              ok,
              `expected count${probe.numbers.length > 1 ? "s" : ""} ${probe.numbers.join(" → ")} not found ${
                probe.numbers.length > 1
                  ? `in that order within ${NUMBER_WINDOW} chars of each other `
                  : ""
              }in ${claim.file}`,
            ).toBe(true);
          }
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
    for (const claim of CLAIMS) {
      const text = fs.readFileSync(path.join(ARTICLE_DIR, claim.file), "utf-8");
      for (const dead of SUPERSEDED) {
        expect(
          text.includes(dead),
          `${claim.file} reasserts the superseded "${dead}"`,
        ).toBe(false);
      }
    }
  });
});

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
          what: "survivor count",
          re: /\(([\d,]+) codes survive\)/,
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
          re: /Di ([\d.]+) codici KBLI classificati, ([\d.]+) sono bloccati/,
          expect: [group(c.total, "."), group(c.blocked, ".")],
        },
        {
          what: "survivor count",
          re: /\(([\d.]+) codici sopravvissuti\)/,
          expect: [group(c.open, ".")],
        },
        {
          what: "closing count",
          re: /supportata da ([\d.]+) codici contati/,
          expect: [group(c.blocked, ".")],
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
          re: /Dari ([\d.]+) kode KBLI terklasifikasi, ([\d.]+) diblokir/,
          expect: [group(c.total, "."), group(c.blocked, ".")],
        },
        {
          what: "survivor count",
          re: /\(([\d.]+) kode bertahan\)/,
          expect: [group(c.open, ".")],
        },
        {
          what: "closing count",
          re: /didukung oleh ([\d.]+) kode yang dihitung/,
          expect: [group(c.blocked, ".")],
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
          const match = text.match(probe.re);
          // A sentence that was reworded is a REAL failure, not a skip: the pin
          // it carried is now unguarded, which is the state this file exists to
          // make impossible.
          expect(
            match,
            `anchor sentence not found in ${claim.file} — it was reworded; re-anchor this probe (${probe.re})`,
          ).not.toBeNull();
          expect(match!.slice(1)).toEqual(probe.expect);
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

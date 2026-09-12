/**
 * The committed interview-walk corpus is REPRODUCIBLE, byte for byte.
 *
 * `apps/backend-rag/.../gold_coverage/fixtures/walks/*.json` is generated data
 * (see `apps/mouth/scripts/visa-oracle/generate-walk-corpus.ts`), and the
 * backend census test `test_interview_walk_census.py` pins an outcome table on
 * top of it. Generated data that nobody can regenerate is hand-written data
 * with extra steps: the moment `flow.ts`, `tree.ts` or `fact-mapper.ts` moves,
 * the corpus is stale and the census is measuring a funnel that no longer
 * exists.
 *
 * So this test runs the REAL generator into a temp dir and compares every byte
 * against what is committed. It goes red on three distinct drifts:
 *   1. the tree/mapper changed and the corpus was not regenerated,
 *   2. a fixture was hand-edited,
 *   3. a walk was added or removed (the file SET is compared too).
 *
 * The cure for a red is always `npm run visa-oracle:walk-corpus`, followed by
 * updating `EXPECTED_OUTCOME` / `WALK_DEAD_END_ALLOWLIST` in the census test.
 */

import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  DEFAULT_OUT_DIR,
  writeWalkCorpus,
} from "../../../../../scripts/visa-oracle/generate-walk-corpus";

/** The corpus size as committed. A PR that adds an interview branch — or, as
 * of PR-5, a new DIMENSION replayed over existing branches — moves it.
 * 43 → 61 on 2026-09-06: `second_home` (2 offshore bases + 1 onshore),
 * `STEPCHILD` (×2 sponsor nationalities), and `diaspora` crossed like the
 * family tile now that it serves the same question sequence (14 walks
 * replacing one). 61 → 67 on PR-5 (2026-09-07): the 5 offshore `retirement`
 * bases plus the onshore neutral `retirement` walk, each replayed a second
 * time at `RETIREMENT_AGE_64_BIRTH_DATE` (age 64) instead of the corpus-wide
 * default 25 — no new tree branch, the same 6 walks answered twice. 67 → 78
 * on PR-D3 (2026-09-13): 11 new walks — the two invest-vehicle
 * below-threshold routes, the three declared-paid-activity branches
 * (employer=no / sponsor=unsure / paid=no), the retirement property/
 * bank_deposit/undecided branches that used to dead-end, and the two
 * STEPCHILD sponsor-permit answers (no/unsure) — see generate-walk-corpus.ts.
 * 78 → 76 on D4a (owner ruling SHWEB-20260911, 2026-09-13): those same two
 * STEPCHILD sponsor-permit walks are retired — no pack requirement for the
 * sponsor's own permit exists for E31D (fresh grader review), so the
 * question and hold they exercised are gone. 76 → 82 on PR-D4d
 * (2026-09-13): 6 new walks — one per seq-21 product with the sponsor.type
 * value that product's rule requires (`offshore/work/sponsor_government`
 * covers E33A/E33B/E23V at once, `offshore/work/sponsor_individual` covers
 * E23U, `offshore/invest/pt_pma/sponsor_government` covers E33C), one
 * proving work item 1's new `other`+paid question end to end
 * (`offshore/other/paid/sponsor_government`), one proving an unresolved
 * answer is silence not a hold (`offshore/work/sponsor_unsure`), and the
 * C6 regression walk (`offshore/other/no_paid_activity/medical`) — see
 * generate-walk-corpus.ts. */
const EXPECTED_WALK_COUNT = 82;

function jsonFilesIn(dir: string): string[] {
  return readdirSync(dir)
    .filter((name) => name.endsWith(".json"))
    .sort();
}

describe("interview-walk corpus is regenerable byte-for-byte", () => {
  const committedDir = DEFAULT_OUT_DIR;
  const committed = jsonFilesIn(committedDir);
  let generatedDir = "";
  let generated: string[] = [];

  beforeAll(async () => {
    generatedDir = mkdtempSync(join(tmpdir(), "visa-oracle-walk-corpus-"));
    await writeWalkCorpus(generatedDir);
    generated = jsonFilesIn(generatedDir);
  }, 60_000);

  afterAll(() => {
    // Only ever the mkdtemp dir this file created — never the committed corpus.
    if (generatedDir) rmSync(generatedDir, { recursive: true, force: true });
  });

  it(`commits ${EXPECTED_WALK_COUNT} walks`, () => {
    expect(committed).toHaveLength(EXPECTED_WALK_COUNT);
  });

  it("generates exactly the committed set of walk files", () => {
    expect(generated).toEqual(committed);
  });

  it.each(committed)(
    "%s is byte-identical to the generator's output",
    (name) => {
      const fromRepo = readFileSync(join(committedDir, name));
      const fromGenerator = readFileSync(join(generatedDir, name));
      // Compare as text first: a mismatch then prints the offending lines rather
      // than two opaque buffers.
      expect(fromGenerator.toString("utf8")).toBe(fromRepo.toString("utf8"));
      expect(fromGenerator.equals(fromRepo)).toBe(true);
    },
  );
});

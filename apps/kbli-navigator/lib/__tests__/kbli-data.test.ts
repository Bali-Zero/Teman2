// =============================================================================
// kbli-data.test.ts — guilt/innocence regression for the quarantine transform.
//
// Context (scar #1 HOME-fork, 2026-07-19): apps/kbli-navigator/data/kbli-2025.json
// used to be an untracked local artifact that rotted to a 2026-03-28 snapshot
// while the canonical KBLI dataset moved on (68112/49213/... code-number
// collisions got quarantined: per_skala -> [], the disputed block preserved
// under per_skala_disputed_<source>, an honest _data_note attached). Now that
// scripts/sync_kbli_dataset.sh keeps this file byte-identical to canonical,
// this test locks in that transformRecord() (lib/kbli-data.ts) handles a
// quarantined record correctly:
//   - GUILT:     a quarantined code (68112) renders NO licensing rows (the
//                disputed block is never resurrected) but the honest-gap
//                intel_2026.whatYouNeed text IS present and readable.
//   - INNOCENCE: a healthy code with real per_skala (55101) renders its
//                licensing rows unchanged.
//
// Run: cd apps/kbli-navigator && npx tsx lib/__tests__/kbli-data.test.ts
// No test framework — plain node:assert, non-zero exit on failure.
// =============================================================================

import assert from "node:assert/strict";
import { getCode, getAllCodes } from "../kbli-data";

function guiltCase() {
  const kbli = getCode("68112");
  assert.ok(kbli, "68112 must be present in the dataset");

  // No licensing rows rendered — the code-collision disputed block must
  // never be resurrected via transformRecord (it only ever reads
  // raw.per_skala, never per_skala_disputed_*).
  assert.deepEqual(
    kbli!.licensing,
    [],
    "68112 (quarantined) must render zero licensing rows, not the disputed PP28/MICE block",
  );

  // Honest-gap prose must be present and legible (this is what the page
  // renders instead of a false risk/license claim for a non-gold code).
  assert.ok(
    kbli!.intel_2026?.whatYouNeed,
    "68112 must carry an intel_2026.whatYouNeed honest-gap explanation",
  );
  assert.match(
    kbli!.intel_2026!.whatYouNeed!,
    /not yet defined|not.{0,15}published|no risk-based/i,
    "68112's whatYouNeed must state the licensing gap honestly, not assert a resolved risk level",
  );

  console.log("PASS guilt: 68112 — empty licensing, honest gap prose present");
}

function innocenceCase() {
  const kbli = getCode("55101");
  assert.ok(kbli, "55101 must be present in the dataset");

  assert.ok(
    kbli!.licensing.length > 0,
    "55101 (healthy code, real per_skala) must render its licensing rows unchanged",
  );
  assert.ok(
    kbli!.licensing[0].riskCategory,
    "55101's primary licensing tier must carry a real risk category",
  );

  console.log(
    `PASS innocence: 55101 — ${kbli!.licensing.length} licensing row(s) rendered unchanged`,
  );
}

function datasetShapeSanity() {
  // Regression for the March-stale fork itself: canonical carries 1,559
  // records, not the old untracked snapshot's 1,563 (4 phantom rows the
  // 2026-03-28 file had that were later removed from canonical).
  const all = getAllCodes();
  assert.equal(
    all.length,
    1559,
    "kbli-2025.json must match canonical's 1,559 records (was 1,563 in the stale March fork)",
  );
  console.log(
    `PASS dataset-shape: ${all.length} records loaded (canonical, not the stale fork)`,
  );
}

guiltCase();
innocenceCase();
datasetShapeSanity();
console.log("\nAll kbli-data.ts quarantine-transform checks passed.");

// =============================================================================
// kbli-gold-content.test.ts — guilt/innocence regression for the collision-code
// gold-content honesty fix (6th surface, task #19, 2026-07-19).
//
// Context: apps/kbli-navigator/lib/kbli-gold-content.ts is a separate,
// ~45K-line hand-authored per-code content file (distinct from apps/mouth's
// gold corpus). It overrides intel_2026/per_skala on the app's [code] page
// for any code with an entry here (page.tsx branches on `gold ? … : …`,
// not on GOLD_CODES tier membership). Two of the 16 quarantined codes with
// an entry here (68112, 49213) asserted stale/wrong risk-tier and licensing
// prose that contradicted the canonical fix already shipped in kbli-data.ts
// (68112 fully detached; 49213 restored with REAL per-ancestor data,
// Menengah Tinggi risk — not the "Low risk" this file used to claim).
//
// Run: cd apps/kbli-navigator && npx tsx lib/__tests__/kbli-gold-content.test.ts
// No test framework — plain node:assert, non-zero exit on failure.
// =============================================================================

import assert from "node:assert/strict";
import { getGoldContent } from "../kbli-gold-content";

function guilt68112() {
  const gold = getGoldContent("68112");
  assert.ok(gold, "68112 must still have a gold-content entry");

  // The old entry OPENED by calling 68112 itself NON-RESIDENTIAL/commercial
  // leasing — the exact opposite of canonical's judul (residential). The
  // new text legitimately mentions "non-residential" once, as a cross-
  // reference to the sibling code 68129 — so match the specific old claim,
  // not the bare substring.
  assert.doesNotMatch(
    gold!.whatItMeans,
    /Leasing or renting out NON-RESIDENTIAL property/,
    "68112 whatItMeans must not open by describing itself as non-residential/commercial",
  );
  assert.match(
    gold!.whatItMeans,
    /^Leasing and operating RESIDENTIAL/,
    "68112 whatItMeans must correctly open by describing this as residential leasing",
  );

  // The old entry asserted a specific risk tier + auto-issuance for the
  // DISPUTED (MICE-collision) per_skala block. Must not resurrect it.
  assert.doesNotMatch(
    gold!.whatYouNeed,
    /Low risk \(Rendah\)\. NIB only, issued \*\*automatically\*\*/,
    "68112 whatYouNeed must not resurrect the disputed MICE per_skala's risk claim",
  );
  assert.match(
    gold!.whatYouNeed,
    /code-number collision/i,
    "68112 whatYouNeed must explain the collision, mirroring canonical's _data_note",
  );
  assert.match(
    gold!.whatYouNeed,
    /not yet defined|has not published/i,
    "68112 whatYouNeed must state the licensing gap honestly",
  );

  console.log(
    "PASS guilt: 68112 gold-content — residential framing + honest gap, no resurrected MICE data",
  );
}

function guilt49213() {
  const gold = getGoldContent("49213");
  assert.ok(gold, "49213 must still have a gold-content entry");

  // The old entry claimed "Low risk (Rendah)" — canonical's RESTORED
  // per-ancestor data says Menengah Tinggi (Medium-High). This is the
  // "align to the restored data" half of the fix (49213 is NOT a gap).
  assert.doesNotMatch(
    gold!.whatYouNeed,
    /Low risk \(Rendah\)/,
    "49213 whatYouNeed must not claim Low risk — the restored data is Menengah Tinggi",
  );
  assert.match(
    gold!.whatYouNeed,
    /Menengah Tinggi/,
    "49213 whatYouNeed must state the restored Medium-High risk tier",
  );
  assert.match(
    gold!.whatYouNeed,
    /NIB dan Sertifikat Standar/,
    "49213 whatYouNeed must state the restored license type verbatim",
  );

  // The old whatItMeans folded in inter-city AKDP as if it were the same
  // activity — exactly the collision the restore corrected.
  assert.doesNotMatch(
    gold!.whatItMeans,
    /inter-city regular routes \(AKDP/,
    "49213 whatItMeans must not describe this as including inter-city AKDP routes",
  );
  assert.match(
    gold!.whatItMeans,
    /INTRA-city/,
    "49213 whatItMeans must state this is an intra-city-only activity",
  );

  console.log(
    "PASS guilt: 49213 gold-content — restored Menengah Tinggi risk, intra-city scope corrected",
  );
}

function innocenceCase() {
  // A gold-tier code with NO canonical quarantine marker must render
  // completely unchanged by this fix.
  const gold = getGoldContent("55101");
  assert.ok(
    gold,
    "55101 (Five-Star Hotel, healthy gold code) must still have an entry",
  );
  assert.ok(
    gold!.whatItMeans.length > 0,
    "55101 whatItMeans must be non-empty",
  );
  assert.doesNotMatch(
    gold!.whatItMeans,
    /code-number collision/i,
    "55101 must not have picked up collision-fix language meant for 68112/49213",
  );

  console.log(
    "PASS innocence: 55101 gold-content unchanged by the collision-code fix",
  );
}

guilt68112();
guilt49213();
innocenceCase();
console.log("\nAll kbli-gold-content.ts collision-code honesty checks passed.");

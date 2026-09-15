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
//                disputed block is never resurrected), and PMA-dependent
//                free-form editorial is withheld while PMA is unverified.
//   - INNOCENCE: a healthy code with real per_skala (55101) renders its
//                licensing rows unchanged.
//
// Run: cd apps/kbli-navigator && npx tsx lib/__tests__/kbli-data.test.ts
// No test framework — plain node:assert, non-zero exit on failure.
// =============================================================================

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PMABadge } from "../../components/kbli/PMABadge";
import {
  discloseBaliL4Record,
  getBaliL4,
  isBlockedInBali,
} from "../kbli-bali-l4";
import { getCode, getAllCodes } from "../kbli-data";
import {
  hasCertifiedCanonicalIntel,
  hasCertifiedStandaloneGold,
  neutralKbliChatOpenerText,
} from "../kbli-editorial-certification";
import {
  getGoldCodes,
  getGoldContent,
  getRawGoldContentForCertification,
} from "../kbli-gold-content";
import {
  disclosePmaInfo,
  formatPmaOwnership,
  hasPublishablePmaCap,
} from "../kbli-pma-disclosure";
import type { KBLIRawCode } from "../kbli-types";

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

  assert.equal(
    kbli!.intel_2026,
    undefined,
    "68112 must withhold free-form editorial while its whole-code PMA verdict is unverified",
  );

  console.log(
    "PASS guilt: 68112 — empty licensing and PMA-dependent editorial withheld",
  );
}

function pmaDisclosureContract() {
  const gap = getCode("01111");
  assert.ok(gap, "01111 must be present in the dataset");
  assert.deepEqual(
    gap!.pma,
    {
      status: "unknown",
      maxForeign: null,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
      verificationStatus: "declared_gap",
      officialBasis: null,
      sourceVintage: null,
      capSpecial: false,
      capVerified: false,
      routeTo: null,
    },
    "01111 must expose one atomic declared-gap PMA shape",
  );
  assert.equal(
    gap!.intel_2026,
    undefined,
    "01111 must not expose free-form editorial derived from an unverified PMA verdict",
  );
  assert.equal(
    getBaliL4("01111"),
    null,
    "01111 must not expose a Bali verdict around the PMA provenance gate",
  );
  assert.equal(isBlockedInBali("01111"), false);

  const located = getCode("02102");
  assert.ok(located, "02102 must be present in the dataset");
  assert.equal(located!.pma.verificationStatus, "located");
  assert.notEqual(located!.pma.status, "unknown");
  assert.ok(located!.pma.officialBasis);
  assert.ok(located!.pma.sourceVintage);
  assert.ok(getBaliL4("02102"), "02102 must retain its located Bali verdict");

  const all = getAllCodes();
  const gaps = all.filter(
    (code) => code.pma.verificationStatus === "declared_gap",
  );
  const locatedCodes = all.filter(
    (code) => code.pma.verificationStatus === "located",
  );
  // SAETTA-20260915 W-H PR-3a: 55201/55203/79903 moved declared_gap→located (Lampiran II), 1505→1502 / 54→57.
  assert.equal(gaps.length, 1502, "dataset must contain 1,502 PMA gaps");
  assert.equal(
    locatedCodes.length,
    57,
    "dataset must contain 57 located PMA verdicts",
  );
  for (const code of gaps) {
    assert.equal(code.pma.status, "unknown", `${code.code}: PMA status`);
    assert.equal(code.pma.maxForeign, null, `${code.code}: PMA cap`);
    assert.equal(code.pma.condition, null, `${code.code}: PMA condition`);
    assert.equal(code.pma.isPriority, false, `${code.code}: PMA priority`);
    assert.equal(code.pma.note, null, `${code.code}: PMA note`);
    assert.equal(code.pma.source, null, `${code.code}: PMA source`);
    assert.equal(code.pma.officialBasis, null, `${code.code}: PMA basis`);
    assert.equal(code.pma.sourceVintage, null, `${code.code}: PMA vintage`);
    assert.equal(code.pma.capSpecial, false, `${code.code}: special cap`);
    assert.equal(code.pma.capVerified, false, `${code.code}: verified cap`);
    assert.equal(code.pma.routeTo, null, `${code.code}: PMA route`);
    assert.equal(code.intel_2026, undefined, `${code.code}: editorial`);
    assert.notEqual(code.tier, "gold", `${code.code}: public content tier`);
  }
  for (const code of locatedCodes) {
    assert.equal(
      hasPublishablePmaCap(code.pma),
      true,
      `${code.code}: located editorial requires an explicitly verified cap`,
    );
  }

  const certifiedIntel = locatedCodes.filter((code) => code.intel_2026);
  assert.equal(
    certifiedIntel.length,
    37,
    "only the 37 manually reviewed canonical editorial blocks may publish (49 - 12 de-certified by W-H PR-3c v3, whose prose still claimed an openness its own tuple denies)",
  );
  for (const code of [
    "10722",
    "47222",
    "50134",
    "73100",
    "96220",
    "10214",
    "16221",
    "22121",
    "47111",
    "50111",
    "50112",
    "51102",
    "55105",
    "65111",
    "79122",
    "95220",
    "96100",
  ]) {
    assert.equal(getCode(code)?.intel_2026, undefined, `${code}: unsafe intel`);
  }

  // standaloneGold lost its OTHER entry, 65121, to W-H PR-3c v3 (its
  // baliContext/zantaraOpener steered a foreign investor to 66221, a
  // declared_gap code, as a "more practical"/"more accessible" route).
  // 47111 lost canonicalIntel in the same PR but its standaloneGold entry
  // is untouched (different content, never flagged) — it is the only code
  // still carrying tier "gold" on this registry.
  assert.equal(getCode("47111")?.tier, "gold");
  assert.notEqual(getCode("65121")?.tier, "gold");
  assert.notEqual(getCode("47221")?.tier, "gold");
  assert.notEqual(getCode("16291")?.tier, "gold");

  console.log(
    `PASS PMA disclosure: ${gaps.length} gaps withheld, ${certifiedIntel.length}/${locatedCodes.length} located editorial blocks certified`,
  );
}

function editorialCertificationContract() {
  const parsed = JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "data", "kbli-2025.json"), "utf8"),
  ) as { data: KBLIRawCode[] };
  const raw = (code: string) => {
    const record = parsed.data.find((item) => item.kode_kbli_2025 === code);
    assert.ok(record, `${code}: raw canonical record`);
    return record;
  };

  // 47111 lost canonicalIntel certification in W-H PR-3c v3 (its prose
  // named 47191/47192 as "fully open to 100% PMA" while both are
  // declared_gap) — its standaloneGold entry is untouched and stays
  // certified (exercised as the positive-path standaloneGold example
  // below). 41016 is a still-certified canonicalIntel example for the
  // positive-path + drift-fails-closed checks here.
  const safe = getCode("41016");
  assert.ok(safe, "41016 transformed record");
  const safeIntel = raw("41016").intel_2026;
  assert.ok(safeIntel, "41016 raw canonical intel");
  assert.equal(
    hasCertifiedCanonicalIntel("41016", safe!.pma, safeIntel),
    true,
    "reviewed canonical bytes and PMA fingerprint must certify",
  );
  assert.equal(
    hasCertifiedCanonicalIntel("41016", safe!.pma, {
      ...safeIntel,
      whatItMeans: `${safeIntel!.whatItMeans}x`,
    }),
    false,
    "one-character editorial drift must fail closed",
  );
  assert.equal(
    hasCertifiedCanonicalIntel(
      "41016",
      { ...safe!.pma, maxForeign: 1 },
      safeIntel,
    ),
    false,
    "PMA fingerprint drift must fail closed",
  );

  // standaloneGold lost 65121 to W-H PR-3c v3 (baliContext/zantaraOpener
  // steered a foreign investor to 66221, a declared_gap code, as a "more
  // practical"/"more accessible" route). 47111's standaloneGold entry is
  // untouched by this PR (only its canonicalIntel was de-certified) and is
  // the sole remaining positive example — exercised directly below instead
  // of a hand-built synthetic registry entry.
  const gold65121 = getCode("65121");
  const gold47111 = getCode("47111");
  assert.ok(gold65121, "65121 transformed record");
  assert.ok(gold47111, "47111 transformed record");
  const decertifiedGold65121 = getRawGoldContentForCertification("65121");
  const certifiedGold47111 = getRawGoldContentForCertification("47111");
  const unsafeGold = getRawGoldContentForCertification("47221");
  assert.ok(decertifiedGold65121, "65121 raw standalone gold");
  assert.ok(certifiedGold47111, "47111 raw standalone gold");
  assert.ok(unsafeGold, "47221 raw standalone gold");
  assert.equal(
    hasCertifiedStandaloneGold("65121", gold65121!.pma, decertifiedGold65121),
    false,
    "de-certified standalone gold must remain withheld",
  );
  assert.equal(
    hasCertifiedStandaloneGold("47111", gold47111!.pma, certifiedGold47111),
    true,
    "47111's untouched standaloneGold entry must still certify",
  );
  assert.equal(
    hasCertifiedStandaloneGold("47221", getCode("47221")!.pma, unsafeGold),
    false,
    "uncorrected standalone gold must remain withheld",
  );
  assert.equal(getGoldContent("47221", getCode("47221")!.pma), null);
  assert.notEqual(
    getGoldContent("47111", gold47111!.pma),
    null,
    "47111's standalone gold must still be served",
  );
  assert.equal(
    getGoldContent("65121", gold65121!.pma),
    null,
    "de-certified standalone gold must be withheld, not served",
  );

  // Binding drift checks against 47111's REAL certified content/PMA tuple
  // (the exact two primitives matchesCertification() /
  // hasCertifiedStandaloneGold() compare: pmaEditorialFingerprint,
  // stableEditorialSha256) — a real registry entry now exists to exercise
  // this against, so no hand-built synthetic entry is needed.
  assert.equal(
    hasCertifiedStandaloneGold("47111", gold47111!.pma, {
      ...certifiedGold47111,
      whatItMeans: `${certifiedGold47111.whatItMeans}x`,
    }),
    false,
    "one-character content drift must break the binding",
  );
  assert.equal(
    hasCertifiedStandaloneGold(
      "47111",
      { ...gold47111!.pma, maxForeign: 1 },
      certifiedGold47111,
    ),
    false,
    "PMA fingerprint drift must break the binding",
  );

  assert.equal(
    safe!.intel_2026?.zantaraOpener,
    neutralKbliChatOpenerText("41016"),
    "published canonical intel must use the compiler-owned neutral opener",
  );

  const goldCodes = getGoldCodes((code) => getCode(code)?.pma);
  assert.deepEqual(
    goldCodes,
    ["47111"],
    "standaloneGold registry retains only 47111 after W-H PR-3c v3 de-certified 65121",
  );
  assert.deepEqual(
    getAllCodes()
      .filter((code) => code.tier === "gold")
      .map((code) => code.code),
    goldCodes,
    "tier assignment must derive from the same certified gold bytes",
  );

  console.log(
    "PASS editorial certification: content hash + PMA fingerprint + neutral opener",
  );
}

function adversarialDisclosureContract() {
  const raw = {
    kode_kbli_2025: "47221",
    pma_status: "TERBATAS",
    pma_max_asing: "49",
    pma_verification_status: "located",
    pma_official_basis: "official locator",
    pma_source_vintage: "2021-05-25",
    pma_prioritas: "false",
    pma_cap_verified: "true",
    l4_bali: {
      status: "OK",
      blocked: "false",
      reason: "must not escape",
    },
  } as unknown as KBLIRawCode;

  assert.deepEqual(
    disclosePmaInfo(raw),
    {
      status: "restricted",
      maxForeign: null,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
      verificationStatus: "located",
      officialBasis: "official locator",
      sourceVintage: "2021-05-25",
      capSpecial: false,
      capVerified: false,
      routeTo: null,
    },
    "public PMA fields must not coerce string caps or booleans",
  );
  assert.equal(
    discloseBaliL4Record(raw as unknown as Record<string, unknown>),
    null,
    "string 'false' must not become a Bali boolean",
  );

  const malformedReview = {
    ...(raw as unknown as Record<string, unknown>),
    pma_max_asing: "special",
    pma_cap_special: true,
    pma_cap_verified: true,
    l4_bali: {
      status: "OK_or_HIGHER_RISK",
      blocked: false,
      needs_review: "false",
      confidence: "FUTURE",
    },
  };
  assert.equal(
    discloseBaliL4Record(malformedReview),
    null,
    "a string review flag must withhold the complete Bali tuple",
  );

  const futureStatus = {
    ...malformedReview,
    l4_bali: {
      status: "FUTURE_STATUS",
      blocked: false,
      needs_review: false,
    },
  };
  assert.equal(
    discloseBaliL4Record(futureStatus),
    null,
    "an unknown status must not become a Bali verdict",
  );

  const valid = {
    ...malformedReview,
    l4_bali: {
      status: "OK_or_HIGHER_RISK",
      blocked: false,
      needs_review: false,
      confidence: "FUTURE",
    },
  };
  assert.equal(
    disclosePmaInfo(valid as unknown as KBLIRawCode).maxForeign,
    "special",
  );
  assert.equal(
    formatPmaOwnership(disclosePmaInfo(raw)),
    "Restricted · ownership cap not verified",
    "a malformed numeric-string cap must never render as null%",
  );
  assert.equal(
    formatPmaOwnership(disclosePmaInfo(valid as unknown as KBLIRawCode)),
    "Special non-percentage conditions",
    "a special cap must never acquire a percentage suffix",
  );

  const locatedOpenWithoutCap = disclosePmaInfo({
    ...(raw as unknown as Record<string, unknown>),
    pma_status: "TERBUKA",
    pma_max_asing: undefined,
  } as unknown as KBLIRawCode);
  assert.equal(
    formatPmaOwnership(locatedOpenWithoutCap),
    "Open · ownership cap not verified",
    "TERBUKA must not synthesize a 100% cap",
  );
  assert.equal(
    formatPmaOwnership(locatedOpenWithoutCap, "metadata"),
    "Open to Foreign Investment (ownership cap not verified)",
    "metadata must not synthesize a 100% cap",
  );
  const locatedOpenUnverifiedCap = disclosePmaInfo({
    ...(raw as unknown as Record<string, unknown>),
    pma_status: "TERBUKA",
    pma_max_asing: 100,
    pma_cap_verified: false,
  } as unknown as KBLIRawCode);
  assert.equal(
    locatedOpenUnverifiedCap.maxForeign,
    null,
    "an unverified numeric cap must be absent from the public model",
  );
  assert.equal(
    formatPmaOwnership(locatedOpenUnverifiedCap),
    "Open · ownership cap not verified",
    "an unverified 100 value must not enter the public ownership verdict",
  );
  assert.equal(
    hasPublishablePmaCap(locatedOpenUnverifiedCap),
    false,
    "generated PMA prose must stay withheld around an unverified cap",
  );

  const locatedRestrictedUnverifiedSpecial = disclosePmaInfo({
    ...(raw as unknown as Record<string, unknown>),
    pma_max_asing: "special",
    pma_cap_special: true,
    pma_cap_verified: false,
  } as unknown as KBLIRawCode);
  assert.equal(
    locatedRestrictedUnverifiedSpecial.maxForeign,
    null,
    "an unverified special cap must be absent from the public model",
  );
  assert.equal(
    formatPmaOwnership(locatedRestrictedUnverifiedSpecial),
    "Restricted · ownership cap not verified",
    "an unverified special marker must not enter the public verdict",
  );
  assert.equal(
    hasPublishablePmaCap(locatedRestrictedUnverifiedSpecial),
    false,
    "generated PMA prose must stay withheld around an unverified special cap",
  );

  const locatedClosedWithoutCap = disclosePmaInfo({
    ...(raw as unknown as Record<string, unknown>),
    pma_status: "TERTUTUP",
    pma_max_asing: null,
    pma_cap_verified: false,
  } as unknown as KBLIRawCode);
  assert.equal(
    formatPmaOwnership(locatedClosedWithoutCap),
    "Closed · ownership cap not verified",
    "a located closed verdict must not hide its unavailable ownership cap",
  );
  assert.equal(
    formatPmaOwnership(locatedClosedWithoutCap, "metadata"),
    "Closed to Foreign Investment (ownership cap not verified)",
  );

  const mismatchedSpecial = disclosePmaInfo({
    ...(raw as unknown as Record<string, unknown>),
    pma_max_asing: 0,
    pma_cap_special: true,
    pma_cap_verified: true,
  } as unknown as KBLIRawCode);
  assert.equal(mismatchedSpecial.maxForeign, 0);
  assert.equal(mismatchedSpecial.capSpecial, false);
  assert.equal(
    formatPmaOwnership(mismatchedSpecial),
    "Closed (0%)",
    "a stray special flag must not override a verified numeric zero",
  );
  assert.deepEqual(discloseBaliL4Record(valid), {
    status: "OK_or_HIGHER_RISK",
    reason: "",
    confidence: "MEDIUM",
    needsReview: false,
    blocked: false,
    from2020: undefined,
    moratorium: { rule: "", effective: "", source: "", virtualOffice: "" },
  });

  console.log("PASS adversarial disclosure: no PMA/Bali type coercion");
}

function componentProvenanceWiringContract() {
  const root = process.cwd();
  const files = ["components/kbli/KBLICard.tsx", "app/kbli/[code]/page.tsx"];
  let callCount = 0;
  for (const relative of files) {
    const source = fs.readFileSync(path.join(root, relative), "utf8");
    const calls = source.match(/<PMABadge[\s\S]*?\/>/g) ?? [];
    assert.ok(calls.length > 0, `${relative}: expected a PMABadge call`);
    for (const call of calls) {
      callCount += 1;
      assert.match(call, /verdictVerified=/, `${relative}: PMA tuple gate`);
      assert.match(call, /capSpecial=/, `${relative}: special-cap marker`);
      assert.match(call, /capVerified=/, `${relative}: cap provenance`);
    }
  }
  assert.equal(callCount, 2, "all two production PMABadge calls are audited");

  const closedWithoutCap = renderToStaticMarkup(
    createElement(PMABadge, {
      status: "closed",
      maxForeign: null,
      verdictVerified: true,
      capVerified: false,
    }),
  );
  assert.match(closedWithoutCap, />Closed</, "closed verdict remains visible");
  assert.match(
    closedWithoutCap,
    /cap not verified/,
    "closed badge must expose an unavailable cap",
  );

  const pageSource = fs.readFileSync(
    path.join(root, "app/kbli/[code]/page.tsx"),
    "utf8",
  );
  assert.match(
    pageSource,
    /gold\?\.zantaraOpener\s*\?\?\s*neutralKbliChatOpenerText\(kbli\.code\)/,
    "every KBLI page must fall back to the exact compiler-owned neutral chat opener",
  );
  assert.doesNotMatch(
    pageSource,
    /opener=\{\s*pmaVerdictVerified\s*\?/,
    "declared-gap pages must not branch to bespoke public opener prose",
  );
  console.log("PASS PMA badge wiring: verdict and cap provenance forwarded");
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
pmaDisclosureContract();
editorialCertificationContract();
adversarialDisclosureContract();
componentProvenanceWiringContract();
datasetShapeSanity();
console.log("\nAll kbli-data.ts quarantine-transform checks passed.");

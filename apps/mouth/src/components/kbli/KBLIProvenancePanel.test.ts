// =============================================================================
// The provenance panel had NO test — and that is how it came to misattribute
// the very thing it exists to disclose.
//
// Its "Bali status" row cited `l4_bali.moratorium.rule` as the SOURCE of every
// Bali verdict and described every one as "Conservative posture derived from the
// risk tier". That rule is not per-code evidence: it is one identical string on
// all 1,559 records. For the codes blocked by an activity-level restriction the
// attribution is simply false, and it was false ON PROD — verified 2026-07-27:
//
//   /kbli/38122  Pengumpulan Limbah Radioaktif   (closed by its sector regulator)
//   /kbli/11010  Industri Penyulingan            (ownership restriction)
//
// both served "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA" as
// their source and "derived from the risk tier" as their basis.
// =============================================================================
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { buildRows } from "./KBLIProvenancePanel";
import { getAllCodes, getCode } from "@/lib/kbli-data";
import { isMoratoriumBasis } from "@/lib/kbli-bali-block";
import type { KBLICode, KBLIProvenance } from "@/lib/kbli-types";

/** Minimal synthetic located-PMA code, for statuses not yet in the live dataset
 * (ATTENZIONE_FASCIA_BALI / l4_bali.closure land with a separate data PR — see
 * W-J B1 spec). Only the fields `buildRows` reads are load-bearing. */
function syntheticLocatedCode(baliL4: KBLICode["baliL4"]): {
  code: KBLICode;
  provenance: KBLIProvenance;
} {
  const provenance: KBLIProvenance = {
    state: "verified",
    definition: { locator: "fixture", assembly: "BPS_7_2025_ONLY" },
    licensing: {
      status: "oss_native",
      locator: "fixture",
      vintage: "2025",
      noOssScope: false,
      contentInheritedFrom: null,
    },
    pma: {
      source: "fixture",
      status: "located",
      locator: "fixture locator",
      vintage: "2026-01-01",
    },
    dataNote: null,
    disputed: null,
  };
  const code = {
    code: "99999",
    titleId: "(fixture)",
    titleEn: "(fixture)",
    baliL4,
    provenance,
  } as unknown as KBLICode;
  return { code, provenance };
}

const baliRow = (code: string) => {
  const kbli = getCode(code);
  expect(kbli, `code ${code} must exist`).toBeDefined();
  const c = kbli as KBLICode;
  expect(c.provenance, `code ${code} must carry provenance`).toBeDefined();
  const provenance = c.provenance as KBLIProvenance;
  expect(
    provenance.pma.status,
    `code ${code} must have located PMA proof`,
  ).toBe("located");
  const row = buildRows(c, provenance).find((r) => r.layer === "Bali status");
  expect(row, `code ${code} must render a Bali status row`).toBeDefined();
  return row!;
};

const pmaRow = (code: string) => {
  const kbli = getCode(code) as KBLICode;
  expect(kbli).toBeDefined();
  return buildRows(kbli, kbli.provenance as KBLIProvenance).find(
    (row) => row.layer === "Foreign ownership (PMA)",
  )!;
};

// SAETTA-20260915 W-J B1 v2 redo (applied onto post-#6596 main):
// cure_l4bali_applied_closure.py rewrote l4_bali.moratorium.rule on all
// 1,559 records, retiring the old blanket string this constant used to
// match ("Bali province blocks ALL Low + Medium-Low risk KBLI for PMA
// (permanent, effective 2026-05-13)") for one that names the actual applied
// closure instead of an unverified date.
const MORATORIUM_RULE = "Bali closed OSS to new PMA licensing";
const RISK_TIER_BASIS = "derived from the risk tier";

describe("the Bali provenance row attributes the verdict to what produced it", () => {
  it("withholds the Bali row when the whole-code PMA verdict is a gap", () => {
    const c = getCode("38122") as KBLICode;
    expect(c.provenance?.pma.status).toBe("declared_gap");
    const row = buildRows(c, c.provenance as KBLIProvenance).find(
      (candidate) => candidate.layer === "Bali status",
    );
    expect(row).toBeUndefined();
  });

  it("withholds the Bali row for every checked declared-gap example", () => {
    // 2026-09-18 naso PR-3: 11010 moved declared_gap→located (named by
    // Perpres 10/2021 Pasal 2(2)(b)); 20119 (TERTUTUP, declared_gap) replaces it.
    for (const code of ["38122", "20119"]) {
      const c = getCode(code) as KBLICode;
      expect(c.provenance?.pma.status, `code ${code}`).toBe("declared_gap");
      expect(c.baliL4, `code ${code}`).toBeUndefined();
      expect(
        buildRows(c, c.provenance as KBLIProvenance).find(
          (candidate) => candidate.layer === "Bali status",
        ),
        `code ${code}`,
      ).toBeUndefined();
    }
  });

  it("GUILT: a located ownership restriction no longer cites the moratorium", () => {
    const row = baliRow("47111");
    expect(row.source).not.toContain(MORATORIUM_RULE);
    expect(row.detail).not.toContain(RISK_TIER_BASIS);
    expect(row.detail).toContain(
      "ownership restriction on the activity itself",
    );
  });

  it("INNOCENCE: a genuine risk-class block keeps the moratorium attribution", () => {
    // SAETTA-20260915 W-J B1 v2 redo: the applied-closure migration
    // reclassified every BLOCCATO_CLASSE_RISCHIO record (mostly into
    // ATTENZIONE_FASCIA_BALI or one of the applied-closure statuses), so it
    // no longer exists in the canonical at all — not a data-coverage gap
    // like NON_CLASSIFICABILE below, a full retirement. CHIUSO_MORATORIA_BALI
    // survives (12 live records) but none currently has a "located" PMA
    // basis, so getAllCodes() cannot surface one either — that IS a coverage
    // gap. Both statuses stay in kbli-bali-block.ts's MORATORIUM_STATUSES/
    // isMoratoriumBasis, so the attribution logic itself is still live and
    // load-bearing; exercised here via the same syntheticLocatedCode()
    // fixture the ATTENZIONE_FASCIA_BALI/CHIUSO_BALI blocks below use, so
    // this stays a real assertion instead of a skip.
    const { code, provenance } = syntheticLocatedCode({
      status: "CHIUSO_MORATORIA_BALI",
      reason: "OSS risk at scale Besar is Rendah/Menengah-Rendah",
      confidence: "HIGH",
      needsReview: false,
      blocked: true,
      moratorium: {
        rule: "Bali closed OSS to new PMA licensing for 18 business fields (KBLI 2020 numbering), not for every low/medium-low risk activity",
        effective: "third week of May 2026",
      },
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    expect(row.source).toContain(MORATORIUM_RULE);
    expect(row.detail).toContain(RISK_TIER_BASIS);
  });

  it("INNOCENCE: a code that is NOT blocked keeps it too — the risk-tier test is what cleared it", () => {
    const open = getAllCodes().find(
      (c) =>
        c.baliL4 &&
        !c.baliL4.blocked &&
        c.baliL4.status !== "NON_CLASSIFICABILE" &&
        c.provenance,
    );
    expect(open).toBeDefined();
    const row = baliRow(open!.code);
    expect(row.source).toContain(MORATORIUM_RULE);
    expect(row.detail).toContain(RISK_TIER_BASIS);
  });

  it("INNOCENCE: a NON_CLASSIFICABILE code keeps its own gap wording, untouched", () => {
    const nc = getAllCodes().find(
      (c) => c.baliL4?.status === "NON_CLASSIFICABILE" && c.provenance,
    );
    if (!nc) return; // none in the current dataset — nothing to protect
    const row = baliRow(nc.code);
    expect(row.verdict).toBe("gap");
    expect(row.detail).toContain("Not classifiable until the true risk tier");
  });

  it("pins the verified population: 53 located-or-sourced-closure codes are blocked by something other than the moratorium", () => {
    const misattributed = getAllCodes().filter(
      (c) =>
        c.baliL4?.blocked === true &&
        !isMoratoriumBasis(c.baliL4.blocked, c.baliL4.status),
    );
    // The public loader exposes Bali only for the exact located+basis+vintage
    // PMA atom. The former 98-record population included unverified Bali
    // verdicts; ten independently adjudicated non-moratorium blocks remain.
    // SAETTA-20260915 W-H PR-3a: 55201/55203/79903 moved declared_gap→located
    // (Perpres 49/2021 Lampiran II allocation), 6→9.
    // SAETTA-20260915 W-J B1 v2 redo: the applied-closure migration also
    // retired BLOCCATO_CLASSE_RISCHIO/CHIUSO_MORATORIA_BALI as the basis for
    // 55105 (one-star hotel, <6,000 m², one of the 18 applied-closure
    // fields) — it moved to CHIUSO_BALI, a non-moratorium status, adding a
    // 10th member that was always "located" but previously WAS
    // moratorium-attributed.
    // SAETTA-20260915 W-J B1 national-cap cure (10 -> 14): the tier->
    // ATTENZIONE conversion had been overriding a record's own NATIONAL
    // pma_* 0%-cap closure; 10214/16221/95220/95299 (pma_status TERBATAS,
    // pma_max_asing 0, located) are kept TERTUTUP/blocked with a
    // field-derived reason instead of being wrongly un-blocked, adding 4
    // more non-moratorium members.
    // 2026-09-16 (W-J B1 disclose, 14 -> 53): `discloseBaliL4` now discloses
    // a Bali APPLIED closure (CHIUSO_BALI, sourced to a public press
    // release) even when the national PMA verdict is not located — the 39
    // `declared_gap` CHIUSO_BALI records (all with a sourced closure.url)
    // that were previously withheld from `getAllCodes()` entirely now carry
    // a `baliL4`, and none of them is moratorium-attributed.
    // W-H PR-3b (53 -> 53, no change): 47249 moves declared_gap -> located
    // (Perpres 49/2021 Lampiran II entry 46). Before this cure it was ALREADY
    // one of the 39 declared_gap/CHIUSO_BALI/closure.url records the disclose
    // change above surfaces, so it was already counted in 53 — becoming
    // "located" does not add it a second time. The other 7 PR-3b codes also
    // move to located, but their l4_bali.status is ATTENZIONE_FASCIA_BALI
    // (blocked: false) — they never qualified and still do not.
    // 2026-09-18 naso PR-3 (53 -> 112): the 59 statutory closures move
    // declared_gap -> located; all are TERTUTUP/0 with l4_bali.status
    // TERTUTUP (blocked: true), so `discloseBaliL4` now discloses them and
    // every one names an ownership restriction, never the moratorium.
    expect(misattributed).toHaveLength(112);
    // Every one of them must now name its own cause, never the risk tier.
    // `baliRow` asserts a LOCATED national PMA tuple, which no longer holds
    // for the 39 newly-disclosed `declared_gap` CHIUSO_BALI members — the
    // whole point of W-J B1 disclose. Use `buildRows` directly instead, and
    // render `source` (a plain string for most statuses, but the CHIUSO_BALI
    // closure citation is a ReactNode with an `<a>` link) to text before
    // substring-checking it.
    for (const c of misattributed) {
      const row = buildRows(c, c.provenance as KBLIProvenance).find(
        (r) => r.layer === "Bali status",
      );
      expect(row, `code ${c.code} must render a Bali status row`).toBeDefined();
      const sourceText =
        typeof row!.source === "string"
          ? row!.source
          : renderToStaticMarkup(row!.source as ReactElement);
      expect(row!.detail, `code ${c.code}`).not.toContain(RISK_TIER_BASIS);
      expect(sourceText, `code ${c.code}`).not.toContain(MORATORIUM_RULE);
    }
  });
});

describe("the Bali provenance row — ATTENZIONE_FASCIA_BALI (added 2026-09-15, W-J B1)", () => {
  it("GUILT: never repeats the 'derived from the risk tier' wording for this status", () => {
    const { code, provenance } = syntheticLocatedCode({
      status: "ATTENZIONE_FASCIA_BALI",
      reason: "not on the closure list",
      confidence: "MEDIUM",
      needsReview: true,
      blocked: false,
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    expect(row.detail).not.toContain(RISK_TIER_BASIS);
    expect(row.detail).toContain("18 business fields");
    expect(row.detail).toContain("verify");
  });

  it("INNOCENCE: a genuinely-cleared non-blocked code (today's data shape) keeps its wording", () => {
    // Guards against a regression that would widen the new branch to every
    // non-blocked status — the pinned INNOCENCE test above (line ~92) already
    // locks this in for TODAY's dataset; this one locks it in for the
    // fixture shape too, so both paths are covered.
    const { code, provenance } = syntheticLocatedCode({
      status: "OK_or_HIGHER_RISK",
      reason: "OK_or_HIGHER_RISK",
      confidence: "HIGH",
      needsReview: false,
      blocked: false,
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    expect(row.detail).toContain(RISK_TIER_BASIS);
  });

  it("GUILT: the `source` field never repeats the old blanket moratorium.rule either (Codex sol MAJOR finding 1, PR #6578)", () => {
    // `isMoratoriumBasis` returns true for ANY non-blocked code by design
    // (see its own docstring), so before this fix the `source` field fell
    // through to `m?.rule` regardless of `isAttentionFascia` — even though
    // `detail` two lines below was already correct. A record that still
    // carries the OLD blanket moratorium object (today's data shape, before
    // the data PR rewrites l4_bali.moratorium on every record) must not
    // print "blocks ALL ... permanent (effective 2026-05-13)" as the SOURCE
    // of a status whose own detail says "does not by itself close this code".
    const { code, provenance } = syntheticLocatedCode({
      status: "ATTENZIONE_FASCIA_BALI",
      reason: "not on the closure list",
      confidence: "MEDIUM",
      needsReview: true,
      blocked: false,
      moratorium: {
        rule: "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA",
        effective: "2026-05-13",
      },
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    expect(row.source).not.toContain("blocks ALL");
    expect(row.source).not.toContain("2026-05-13");
    expect(row.source).toContain("18 business fields");
  });
});

describe("the Bali provenance row — CHIUSO_BALI closure citation (added 2026-09-15, W-J B1)", () => {
  it("INNOCENCE: instrument + code list render as links, ancestors are named", () => {
    const { code, provenance } = syntheticLocatedCode({
      status: "CHIUSO_BALI",
      reason: "closed to new PMA licensing",
      confidence: "HIGH",
      needsReview: false,
      blocked: true,
      closure: {
        instrument: "Pemprov Bali press release",
        url: "https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss",
        listSource: "ANTARA Bali",
        listUrl: "https://bali.antaranews.com/berita/410161",
        ancestors2020: ["55110", "55120"],
      },
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    const html = renderToStaticMarkup(row.source as ReactElement);
    expect(html).toContain(
      'href="https://www.baliprov.go.id/web/gubernur-koster-batasi-akses-oss"',
    );
    expect(html).toContain('href="https://bali.antaranews.com/berita/410161"');
    expect(html).toContain("Pemprov Bali press release");
    expect(html).toContain("ANTARA Bali");
    expect(html).toContain("KBLI 2020 55110, 55120, BPS conversion table");
  });

  it("GUILT: a rejected (non-http) url never reaches the panel as a link", () => {
    // discloseBaliL4 is the ONLY gate — a closure object handed to the panel
    // pre-validated (as it always is in production) with a null url must not
    // render an <a> tag; the instrument text still renders.
    const { code, provenance } = syntheticLocatedCode({
      status: "CHIUSO_BALI",
      reason: "closed to new PMA licensing",
      confidence: "HIGH",
      needsReview: false,
      blocked: true,
      closure: {
        instrument: "Pemprov Bali press release",
        url: null,
        listSource: "ANTARA Bali",
        listUrl: null,
      },
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    const html = renderToStaticMarkup(row.source as ReactElement);
    expect(html).not.toContain("<a ");
    expect(html).toContain("Pemprov Bali press release");
    expect(html).toContain("ANTARA Bali");
  });

  it("INNOCENCE: CHIUSO_BALI without a closure object keeps current behaviour", () => {
    const { code, provenance } = syntheticLocatedCode({
      status: "CHIUSO_BALI",
      reason: "closed to new PMA licensing",
      confidence: "HIGH",
      needsReview: false,
      blocked: true,
    });
    const row = buildRows(code, provenance).find(
      (r) => r.layer === "Bali status",
    )!;
    // Falls through to the existing non-moratorium-basis wording, unchanged.
    expect(row.source).toBe(
      "Activity-level restriction — not the risk-tier moratorium overlay",
    );
  });
});

describe("the Bali provenance row — an unlocated sourced closure discloses on its own evidence (added 2026-09-16, W-J B1 disclose)", () => {
  it("INNOCENCE: 68111 (national PMA verdict still declared_gap) renders the Bali status row with the press-release link", () => {
    const kbli = getCode("68111") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4?.status).toBe("CHIUSO_BALI");
    const row = buildRows(kbli, kbli.provenance as KBLIProvenance).find(
      (r) => r.layer === "Bali status",
    );
    expect(row).toBeDefined();
    const html = renderToStaticMarkup(row!.source as ReactElement);
    expect(html).toContain("<a ");
    expect(html).toContain("baliprov.go.id");
  });

  it("GUILT: a genuinely unlocated, non-sourced-closure code (62900) still withholds the row", () => {
    // 01192 was this test's example until naso PR-5 (residual lot 2) located
    // it. 62900 carries the same ATTENZIONE_FASCIA_BALI status and stays
    // declared_gap (withheld by that lot's legacy_pma_prose leg).
    const kbli = getCode("62900") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4).toBeUndefined();
    const row = buildRows(kbli, kbli.provenance as KBLIProvenance).find(
      (r) => r.layer === "Bali status",
    );
    expect(row).toBeUndefined();
  });
});

describe("the PMA provenance row follows the canonical verification state", () => {
  // 2026-09-18 naso PR-3: 01287 moved declared_gap→located (UU 25/2007
  // Pasal 12(2) item, statutory closure); 20119 (TERTUTUP, declared_gap,
  // BPS ancestors 20111/20114) is the exemplar now.
  it("guilt: 20119 renders a declared gap, not a crosswalk promise", () => {
    const row = pmaRow("20119");
    expect(row.verdict).toBe("gap");
    expect(row.vintage).toBe("—");
    expect(row.detail).toContain("declares a verification gap");
    expect(row.detail).not.toContain("in progress");
  });

  it("innocence: a located sector-law code renders verified locator + vintage", () => {
    const row = pmaRow("65111");
    expect(row.verdict).toBe("verified");
    expect(row.vintage).toBe("2020-01-20");
    expect(row.locator).toContain("PP 14/2018 Pasal 5(1)");
    expect(row.detail).toContain("adjudicated official basis");
  });
});

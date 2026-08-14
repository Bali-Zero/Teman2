import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import {
  baliBlockClause,
  shouldShowReason,
  containsItalian,
  isProposalOnly,
  narratesUnverifiedRoute,
  baliBlockedHint,
  isNationalClosure,
  nationalClosureBasis,
} from "./kbli-bali-block";
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";
import goldData from "../../data/kbli-gold-all.json";
import { buildKbliFaq } from "./kbli-faq";
import type { KBLICode } from "./kbli-types";

interface RawL4 {
  blocked?: boolean;
  status?: string;
  reason?: string;
}
interface RawRecord {
  kode_kbli_2025: string;
  l4_bali?: RawL4;
  per_skala?: unknown[];
  pma_status?: string;
  pma_max_asing?: number;
  pma_source?: string | null;
  pma_official_basis?: string | null;
  pma_source_vintage?: string | null;
  pma_verification_status?: "located" | "declared_gap";
  pma_cap_special?: boolean;
}
const RECORDS = (rawData as { data: RawRecord[] }).data;
const BLOCKED = RECORDS.filter((r) => r.l4_bali?.blocked === true);
const GOLD = goldData as unknown as Record<string, { whatYouNeed?: string }>;

const MORATORIUM_SENTENCE = "under the 13 May 2026 moratorium";

// The FAQ reads a transformed `KBLICode`, and `transformCode` is module-private
// in the loader. Rather than export internals for a test, this builds the exact
// subset `buildKbliFaq` touches — and takes every load-bearing value FROM THE
// LIVE RECORD, so the fixture cannot drift into fiction while the catalogue moves
// underneath it. The fields the PMA answer does not read are inert placeholders.
function toKbliCodeForFaq(r: RawRecord): KBLICode {
  return {
    code: r.kode_kbli_2025,
    titleId: "(judul)",
    titleEn: "(title)",
    titleEnIsReal: false,
    section: "A",
    licensing: [],
    transition: {
      mappingStatus: null,
      mappingNote: null,
      pp28LicensingSourceCodes: [],
    },
    pma: {
      status:
        r.pma_status === "TERBUKA"
          ? "open"
          : r.pma_status === "TERBATAS"
            ? "restricted"
            : "closed",
      maxForeign: r.pma_max_asing ?? null,
      source: r.pma_source ?? null,
      verificationStatus: r.pma_verification_status ?? "declared_gap",
      officialBasis: r.pma_official_basis ?? null,
      sourceVintage: r.pma_source_vintage ?? null,
      capVerified: false,
      capSpecial: r.pma_cap_special ?? false,
      condition: null,
    },
    baliL4: r.l4_bali?.status
      ? {
          status: r.l4_bali.status,
          reason: r.l4_bali.reason ?? null,
          blocked: r.l4_bali.blocked ?? false,
        }
      : null,
    provenance: {
      state: "pending",
      definition: { locator: null, assembly: null },
      licensing: {
        status: "pending_crosswalk",
        locator: null,
        vintage: null,
        noOssScope: true,
        contentInheritedFrom: null,
      },
      pma: {
        source: r.pma_source ?? null,
        status: r.pma_verification_status ?? "declared_gap",
        locator: r.pma_official_basis ?? null,
        vintage: r.pma_source_vintage ?? null,
      },
      dataNote: null,
      disputed: null,
    },
  } as unknown as KBLICode;
}

describe("baliBlockClause — the cause is derived, never defaulted", () => {
  it("GUILT: a non-moratorium block never claims the moratorium", () => {
    // The defect: every status except CHIUSO_PMA_NO_BESAR fell through to the
    // moratorium sentence. These four are the ones that were wrong on prod.
    for (const status of [
      "TERTUTUP",
      "CHIUSO_REGOLATORE_SETTORIALE",
      "CHIUSO_BALI",
      "CHIUSO_BALI_PROPOSTO",
    ]) {
      expect(baliBlockClause(status)).not.toContain(MORATORIUM_SENTENCE);
    }
  });

  it("INNOCENCE: the two real moratorium statuses still say so", () => {
    expect(baliBlockClause("BLOCCATO_CLASSE_RISCHIO")).toContain(
      MORATORIUM_SENTENCE,
    );
    expect(baliBlockClause("CHIUSO_MORATORIA_BALI")).toContain(
      MORATORIUM_SENTENCE,
    );
  });

  it("INNOCENCE: the pre-existing MSME special case is unchanged", () => {
    expect(baliBlockClause("CHIUSO_PMA_NO_BESAR")).toContain(
      "reserved for micro/small/medium enterprises",
    );
  });

  it("GUILT: an unknown status names no cause at all", () => {
    // A declared gap beats a confident wrong answer. The old code's failure mode
    // was precisely that its fallback asserted a cause.
    const clause = baliBlockClause("SOME_STATUS_ADDED_UPSTREAM_LATER");
    expect(clause).not.toContain(MORATORIUM_SENTENCE);
    expect(clause).not.toMatch(/because|under the|reserved for/i);
  });

  it("a PROPOSED closure is never stated as in force", () => {
    const clause = baliBlockClause("CHIUSO_BALI_PROPOSTO");
    expect(clause).toContain("not yet in force");
    expect(isProposalOnly("CHIUSO_BALI_PROPOSTO")).toBe(true);
    expect(isProposalOnly("CHIUSO_BALI")).toBe(false);
  });
});

describe("shouldShowReason — a cause and its denial must not share a sentence", () => {
  const TEST_NOTE =
    "OSS risk at scale Besar is Menengah-Tinggi/Tinggi → not blocked by moratorium";

  it("GUILT: the moratorium-test note is dropped when the cause is not the moratorium", () => {
    expect(shouldShowReason("TERTUTUP", TEST_NOTE)).toBe(false);
  });

  it("INNOCENCE: the same note is kept when the cause IS the moratorium", () => {
    // Suppression is conditional on the cause. Dropping it unconditionally would
    // strip the explanation from the 372 codes the moratorium really blocks.
    expect(shouldShowReason("BLOCCATO_CLASSE_RISCHIO", TEST_NOTE)).toBe(true);
  });

  it("INNOCENCE: a reason that explains the bar is always kept", () => {
    expect(
      shouldShowReason(
        "TERTUTUP",
        "Legal services are reserved for Indonesian-licensed advocates (UU 18/2003 on Advocates).",
      ),
    ).toBe(true);
  });

  it("GUILT: an Italian reason never reaches a client-facing English page", () => {
    expect(
      shouldShowReason(
        "TERTUTUP",
        "Notaio/PPAT è ufficio personale e statale, solo WNI (UU 30/2004 mod. UU 2/2014). PMA impossibile.",
      ),
    ).toBe(false);
    expect(
      shouldShowReason(
        "CHIUSO_BALI_PROPOSTO",
        "travel agency: proposto chiusura",
      ),
    ).toBe(false);
  });

  it("INNOCENCE: 'solo practice' is English and must survive the Italian guard", () => {
    // The first draft of the marker list included \bsolo\b and would have eaten
    // this — the reason carrying the most useful referral in the corpus.
    const medical =
      "TERTUTUP to WNA under Kemenkes health law — a foreign specialist cannot open a solo practice; for PMA use 86103 (klinik, TERBATAS 67%).";
    expect(containsItalian(medical)).toBe(false);
    expect(shouldShowReason("TERTUTUP", medical)).toBe(true);
  });

  it("an empty or missing reason is simply not rendered", () => {
    expect(shouldShowReason("TERTUTUP", "")).toBe(false);
    expect(shouldShowReason("TERTUTUP", null)).toBe(false);
    expect(shouldShowReason("TERTUTUP", undefined)).toBe(false);
  });
});

describe("the real dataset — the invariant that was broken on prod", () => {
  it("every blocked status has a clause, and only moratorium ones cite the moratorium", () => {
    const statuses = new Set(BLOCKED.map((r) => r.l4_bali?.status ?? ""));
    expect(statuses.size).toBeGreaterThan(1);
    for (const status of statuses) {
      const clause = baliBlockClause(status);
      expect(clause.length).toBeGreaterThan(10);
      if (clause.includes(MORATORIUM_SENTENCE)) {
        expect(["BLOCCATO_CLASSE_RISCHIO", "CHIUSO_MORATORIA_BALI"]).toContain(
          status,
        );
      }
    }
  });

  it("no blocked page can render a clause and a reason that contradict each other", () => {
    // The prod defect, pinned: clause says moratorium, spliced reason says
    // "not blocked by moratorium". Zero records may produce that pairing.
    const contradictions = BLOCKED.filter((r) => {
      const status = r.l4_bali?.status;
      const reason = r.l4_bali?.reason ?? "";
      const clause = baliBlockClause(status);
      return (
        clause.includes(MORATORIUM_SENTENCE) &&
        shouldShowReason(status, reason) &&
        /not\s+blocked\s+by\s+moratorium/i.test(reason)
      );
    });
    expect(contradictions.map((r) => r.kode_kbli_2025)).toEqual([]);
  });

  it("no Italian reaches a rendered reason on any blocked code", () => {
    const italian = BLOCKED.filter((r) =>
      shouldShowReason(r.l4_bali?.status, r.l4_bali?.reason ?? ""),
    ).filter((r) => containsItalian(r.l4_bali?.reason ?? ""));
    expect(italian.map((r) => r.kode_kbli_2025)).toEqual([]);
  });
});

describe("narratesUnverifiedRoute — a route the page says has no basis", () => {
  // Verbatim from /kbli/86202's gold walkthrough, step 3, on prod today.
  const REAL_ROUTE =
    "3. **NIB + Standard Certificate** (Micro / Small / Medium / Large, Medium-High risk) — Authority: Bupati/Walikota — 25 Hari";

  it("GUILT: zero served rows + a tier and an authority = framed", () => {
    expect(narratesUnverifiedRoute(0, REAL_ROUTE)).toBe(true);
  });

  it("INNOCENCE: the same text is fine when rows actually survive", () => {
    // 49213 and 93191 assert tiers their surviving rows still support. The
    // frame must not accuse a page whose basis is intact.
    expect(narratesUnverifiedRoute(12, REAL_ROUTE)).toBe(false);
    expect(narratesUnverifiedRoute(1, REAL_ROUTE)).toBe(false);
  });

  it("INNOCENCE: an honest-gap walkthrough is not framed twice", () => {
    // 36 of the 44 zero-row gold entries already read as declared gaps. A tier
    // NAME appearing inside such a sentence must not trip the frame on its own.
    expect(
      narratesUnverifiedRoute(
        0,
        "**Licensing:** not yet reliably defined for this code. The risk tier and licensing procedure shown here earlier were carried over from an unrelated served record, so they have been removed from this page.",
      ),
    ).toBe(false);
  });

  it("INNOCENCE: an authority with no tier is not a route", () => {
    expect(
      narratesUnverifiedRoute(
        0,
        "Sectoral oversight sits with the Menteri; the risk classification is not yet published for this code.",
      ),
    ).toBe(false);
  });

  it("an empty or missing walkthrough is never framed", () => {
    expect(narratesUnverifiedRoute(0, "")).toBe(false);
    expect(narratesUnverifiedRoute(0, null)).toBe(false);
    expect(narratesUnverifiedRoute(0, undefined)).toBe(false);
  });

  it("pins the live population: 0 of the 44 zero-row gold pages", () => {
    // (see the PMA-verdict-banner block below for the second render site)
    // Measured on the canonical + gold of 2026-07-27, re-measured 2026-08-05.
    // Pinned so that widening or narrowing the frame is a visible, deliberate
    // change rather than a silent one — the same discipline as the
    // untraceable-PMA pin.
    //
    // 8 -> 1 on 2026-08-05, and the pin earned its keep by making that visible.
    // `cure_prose_unverifiable_tier.py` removed the narrated route from seven of
    // the eight (72101, 75001, 75002, 75009, 86109, 86203, 91222): each is in
    // that cure's spec, each carried gold prose walking a client through a
    // licensing path the same page declared unverifiable.
    //
    // 1 -> 0 on 2026-08-05, same day, by the second lane. The note this replaces
    // said 86202 survived "ON PURPOSE", belonging to the separate family where a
    // NATIONAL closure is recorded in the Bali field while `pma_status` stays
    // TERBUKA at 100% (the family of 64110, Bank Sentral) — and that curing it
    // "means deciding what the national ceiling should say, which is not this
    // cure's business." `cure_national_ceiling_framing.py` is that business:
    // 86202's gold walkthrough no longer offers a PT-PMA/NIB route beneath a
    // sentence saying solo practice is closed to foreign nationals.
    //
    // AN EMPTY LIVE SET IS NOT A VACUOUS ASSERTION HERE, and that is worth
    // stating because normally it would be: a filter that always returned []
    // would satisfy this line. Two things keep it honest. `zeroRow.length` is
    // still asserted at 44, so the denominator is computed from the real
    // canonical + gold and a broken data path fails loudly. And guilt for
    // `narratesUnverifiedRoute` itself is carried by the synthetic cases above
    // ("a zero-row page that still walks a client through a licensing path" and
    // the authority/tier pair), which fail if the detector stops detecting.
    // If a future record re-enters this set, this line goes red — which is the
    // whole point of pinning a population rather than a count.
    const goldMap = GOLD as Record<
      string,
      { whatYouNeed?: string } | undefined
    >;
    const zeroRow = RECORDS.filter(
      (r) =>
        (r.per_skala ?? []).length === 0 &&
        !!goldMap[r.kode_kbli_2025]?.whatYouNeed,
    );
    const framed = zeroRow.filter((r) =>
      narratesUnverifiedRoute(0, goldMap[r.kode_kbli_2025]?.whatYouNeed),
    );
    expect(zeroRow.length).toBe(44);
    expect(framed.map((r) => r.kode_kbli_2025).sort()).toEqual([]);
  });
});

describe("the PMA verdict banner — the SECOND render site", () => {
  // Found only because the prove-live control (01192, BLOCCATO_CLASSE_RISCHIO)
  // showed no licensing frame at all: it renders a different notice, at the top
  // of the page, with its own hardcoded copy. That copy asserted ONE cause —
  // "reserved for MSMEs" — for every blocked code, while the Bali badge a few
  // lines below derived the real one. 01192 said "reserved for MSMEs" and
  // "Blocked in Bali (risk-class moratorium)" in the same viewport.
  const HERE = dirname(fileURLToPath(import.meta.url));
  const PAGE = readFileSync(
    join(HERE, "..", "app", "kbli", "[code]", "page.tsx"),
    "utf8",
  );

  it("GUILT: the banner no longer hardcodes a single cause", () => {
    expect(PAGE).not.toContain("reserved for MSMEs; a PT PMA");
  });

  it("the banner derives its cause from the same total function", () => {
    expect(PAGE).toContain("baliBlockClause(kbli.baliL4?.status)");
  });

  it("pins the population: 455 render the notice, only 7 are MSME-reserved", () => {
    // Mirrors the component's own guard: baliBlocked && !nationallyClosed.
    const nationallyClosed = (r: RawRecord) =>
      r.pma_cap_special !== true &&
      ((r.pma_status ?? "").toUpperCase() === "TERTUTUP" ||
        (r.pma_max_asing ?? 0) === 0);
    const notice = RECORDS.filter(
      (r) => r.l4_bali?.blocked === true && !nationallyClosed(r),
    );
    const msme = notice.filter(
      (r) => r.l4_bali?.status === "CHIUSO_PMA_NO_BESAR",
    );
    // 456 until 2026-08-01, when the Perpres 49/2021 Lampiran III cure gave
    // twenty codes their lawful foreign cap. Exactly ONE of them is also
    // Bali-blocked — 16221 (Industri Barang Bangunan dari Kayu), now 0%
    // foreign — so it stops qualifying for a notice whose whole job is to
    // explain a BALI-specific cause. The binding cause for 16221 is national
    // now, and the national layer says it. The other nineteen sit at 49%,
    // which is not 0, so they stay. A drop of one after patching twenty is
    // the expected shape here, not a rounding accident.
    //
    // 39 → 7 on 2026-08-03. The MSME-reserved count was never a count of
    // reservations: 32 of the 39 earned that status from "OSS holds no Usaha
    // Besar scale row, therefore reserved for UMKM", an inference Permeninves/
    // BKPM 5/2025 Pasal 26(1) inverts — being Usaha Besar is a CONSEQUENCE of
    // PMA status, not a precondition for it. Each of the 39 was adjudicated
    // against Perpres 49/2021 Lampiran II directly; SEVEN are genuinely
    // allocated to Koperasi/UMKM and keep the status, the other 32 moved to
    // the cause that actually blocks them. The notice total does NOT move:
    // they are all still Bali-blocked, so this is a re-attribution, not an
    // opening. If a future change moves `notice` too, that is a different
    // event and this test should fail rather than absorb it.
    //
    // 455 -> 451 and 7 -> 6 on 2026-08-06, and this is the "different event"
    // the paragraph above demanded be argued rather than absorbed. The Lampiran
    // II re-adjudication reserved nine codes at 0% foreign; FOUR of them
    // (10214, 95220, 95291, 95299) are also Bali-blocked, so by the same rule
    // that removed 16221 they now leave a notice whose whole job is to explain
    // a BALI-specific cause — theirs is national.
    //
    // The msme drop is the one worth reading: 95291 carried
    // CHIUSO_PMA_NO_BESAR, i.e. the Bali layer already said "reserved for
    // Koperasi/UMKM" while the national layer published it 100% open. That
    // contradiction is what the cure closed. The code did not become freer; the
    // two layers stopped disagreeing, and the national one now carries it.
    // 451 -> 448 and 6 -> 3 on 2026-08-06 (second movement the same day), and
    // it is the same event argued once more rather than absorbed. The
    // SPLIT-HEIR cure reserved four more codes at 0%; THREE of them — 96210
    // barbering, 96220 beauty care, 96100 laundry — are Bali-blocked, so by the
    // rule that removed 16221 and the previous four, they leave a notice whose
    // job is to explain a BALI-specific cause. Theirs is national.
    //
    // The fourth cured code, 55105 (one-star hotel), is absent from every count
    // in this file and that is correct, not an oversight: its l4_bali.blocked
    // is false, so it was never in `blocked` to begin with. Four codes cured,
    // three departures — twice over, since the Pasal 7(1) queue moved by three
    // for its own unrelated reason.
    //
    // Read the two drops TOGETHER, because that is where the meaning is: all
    // three left `notice` AND all three left `msme`, so the difference below is
    // UNCHANGED at 445. That is the signature of the Bali layer and the
    // national layer ceasing to disagree — each of the three carried
    // CHIUSO_PMA_NO_BESAR, i.e. Bali already said "reserved for Koperasi/UMKM"
    // while the national fields published 100% open. Nothing became freer. Had
    // 445 moved, codes would have left the notice for some cause other than
    // gaining a national one, and that would be a different event again.
    expect(notice.length).toBe(448);
    expect(msme.length).toBe(3);
    // 445 pages carry the notice for a cause other than an MSME reservation.
    expect(notice.length - msme.length).toBe(445);
  });

  it("the count above is a SUBTRACTION, and names what it subtracted", () => {
    // Deliberately not `notice.filter(nationallyClosed) === []`: `notice` is
    // DEFINED as blocked && !nationallyClosed, so that assertion is empty by
    // construction and would pass against any dataset whatsoever. This one
    // decomposes the population instead, so it fails if 16221 ever regains a
    // non-zero cap (the Perpres cure regressed) and it fails if the split
    // stops adding up.
    const nationallyClosed = (r: RawRecord) =>
      r.pma_cap_special !== true &&
      ((r.pma_status ?? "").toUpperCase() === "TERTUTUP" ||
        (r.pma_max_asing ?? 0) === 0);
    const blocked = RECORDS.filter((r) => r.l4_bali?.blocked === true);
    const excluded = blocked.filter(nationallyClosed);
    expect(excluded.map((r) => r.kode_kbli_2025)).toContain("16221");
    // …and the four the Lampiran II cure sent the same way, for the same
    // reason: a 0% national cap outranks a Bali-scoped explanation.
    for (const code of ["10214", "95220", "95291", "95299"]) {
      expect(excluded.map((r) => r.kode_kbli_2025)).toContain(code);
    }
    // …and the three the SPLIT-HEIR cure sent the same way on 2026-08-06. Named
    // rather than counted, for the same reason as the four above: a population
    // that only has a size cannot be checked by the pass that closes it.
    for (const code of ["96210", "96220", "96100"]) {
      expect(excluded.map((r) => r.kode_kbli_2025)).toContain(code);
    }
    expect(blocked.length - excluded.length).toBe(448);
    // and it left by CAP, not by status — the status is TERBATAS, which the
    // banner's guard does not look at
    const woodBuilding = RECORDS.find((r) => r.kode_kbli_2025 === "16221");
    expect(woodBuilding?.pma_max_asing).toBe(0);
    expect((woodBuilding?.pma_status ?? "").toUpperCase()).toBe("TERBATAS");
  });

  it("INNOCENCE: the 39 MSME-reserved codes keep their original meaning", () => {
    expect(baliBlockClause("CHIUSO_PMA_NO_BESAR")).toContain(
      "reserved for micro/small/medium enterprises",
    );
  });

  it("the assistant's opening line derives its cause too", () => {
    // This string seeds the chat context on a blocked code, so a wrong cause
    // here becomes a wrong cause in the ANSWER. It used to hedge two at once:
    // "(reserved UMKM / 2026 moratorium)".
    expect(PAGE).not.toContain("reserved UMKM / 2026 moratorium");
    expect(PAGE).toContain(
      "in Bali this code is currently ${baliBlockClause(kbli.baliL4?.status)}",
    );
  });

  it("the PMA trailing line names NO cause rather than the wrong one", () => {
    // rewritePmaLineForBali only receives `baliBlocked`, never the status, so
    // it cannot derive a cause — it must not assert one either. The frame
    // directly above it does the deriving.
    const SECTION = readFileSync(
      join(HERE, "..", "components", "kbli", "LicensingSection.tsx"),
      "utf8",
    );
    expect(SECTION).not.toContain(
      "BLOCKED for a PT PMA in Bali (reserved UMKM / moratorium)",
    );
    expect(SECTION).toContain("but not open to a PT PMA in Bali");
  });
});

describe("the FAQ + FAQPage JSON-LD — the THIRD render site in this file, FIFTH overall", () => {
  // Missed by the L2.10 sweep because it looked for the licensing frame's
  // wording; `kbli-faq.ts` carried its own hardcoded copy. Curing the banner
  // without this one did not leave the FAQ stale — it put the two in
  // CONTRADICTION on the same page, which is worse than either alone.
  const HERE = dirname(fileURLToPath(import.meta.url));
  const FAQ = readFileSync(join(HERE, "kbli-faq.ts"), "utf8");

  it("GUILT: the builder no longer hardcodes a cause", () => {
    expect(FAQ).not.toContain("(reserved for UMKM / 2026 moratorium)");
  });

  it("it derives the cause, and gates the reason, with the same two functions", () => {
    expect(FAQ).toContain("baliBlockClause(code.baliL4?.status)");
    expect(FAQ).toContain("shouldShowReason(code.baliL4?.status");
  });

  it("pins the population: 454 answers, only 7 are MSME-reserved", () => {
    // Mirrors the builder's own guard: pma.status === "open" && baliL4.blocked.
    // Only the exact canonical TERBUKA token maps to open.
    const openNationally = (r: RawRecord) => {
      const s = (r.pma_status ?? "").toUpperCase();
      return s === "TERBUKA";
    };
    const answers = BLOCKED.filter(openNationally);
    const msme = answers.filter(
      (r) => r.l4_bali?.status === "CHIUSO_PMA_NO_BESAR",
    );
    // 455 until 2026-08-01 — same single departure as the banner above
    // (16221), reached by a DIFFERENT predicate: there it left because its cap
    // became 0, here because its status became TERBATAS. Two guards, two
    // reasons, one code; that they agree on this record is a coincidence of
    // the cure, not evidence the populations are the same. The test below
    // still proves they are not.
    //
    // 39 → 7 on 2026-08-03, for the reason given at the banner pin above: the
    // no-Usaha-Besar-row inference was withdrawn and each of the 39 codes was
    // adjudicated against the annex. This site reaches the SAME seven, by a
    // different predicate — which is what makes it worth pinning separately.
    //
    // 454 -> 450 and 7 -> 6 on 2026-08-06: the SAME four codes as the banner
    // (10214, 95220, 95291, 95299), and again by the other predicate — there
    // they left because their cap became 0, here because their status became
    // TERBATAS. The two guards agreeing on all four is once more a property of
    // this particular cure, which writes both fields in one go, and not
    // evidence that the populations have merged. The subset test below still
    // proves they have not.
    // 450 -> 447 and 6 -> 3 on 2026-08-06: the SAME three codes as the banner
    // (96210, 96220, 96100) reaching this site by the OTHER predicate — there
    // they left because their cap became 0, here because their status became
    // TERBATAS. As with the previous cure, the two guards agreeing on all three
    // is a property of a cure that writes both fields in one go, not evidence
    // that the two populations have merged; the subset test below still proves
    // they have not. And again the difference is UNCHANGED at 444, because the
    // three left both sets together.
    expect(answers.length).toBe(447);
    expect(msme.length).toBe(3);
    // 444 answers carry the block for a cause other than an MSME reservation —
    // in the visible Q&A and in the FAQPage JSON-LD, the copy that leaves the
    // site.
    expect(answers.length - msme.length).toBe(444);
  });

  it("this site is a SUBSET of the banner's — a cure for one is not a cure for the other", () => {
    // Establishes they are different populations, so neither pin can be
    // derived from the other and a future edit cannot silently merge them.
    const nationallyClosed = (r: RawRecord) =>
      r.pma_cap_special !== true &&
      ((r.pma_status ?? "").toUpperCase() === "TERTUTUP" ||
        (r.pma_max_asing ?? 0) === 0);
    const banner = BLOCKED.filter((r) => !nationallyClosed(r));
    const faq = BLOCKED.filter((r) => {
      const s = (r.pma_status ?? "").toUpperCase();
      return s !== "TERBATAS" && s !== "TERTUTUP";
    });
    const bannerCodes = new Set(banner.map((r) => r.kode_kbli_2025));
    const onlyFaq = faq.filter((r) => !bannerCodes.has(r.kode_kbli_2025));
    expect(onlyFaq).toHaveLength(0);
    expect(banner.length - faq.length).toBe(1);
  });
});

describe("baliBlockedHint — the index card must not blame the moratorium for every block", () => {
  // The card said "low and medium-low-risk activities are treated as closed"
  // over a percentage covering 518 codes, 111 of which are blocked by something
  // else entirely. That is the same over-attribution `isMoratoriumBasis` was
  // added to prevent on the per-code page (cured 2026-07-27); the card was
  // missed, so the cure covered one consumer of the same fact and not the other.
  const moratorium = (n: number) =>
    Array.from({ length: n }, () => ({
      baliL4: { status: "BLOCCATO_CLASSE_RISCHIO", blocked: true },
    }));
  const scale = (n: number) =>
    Array.from({ length: n }, () => ({
      baliL4: { status: "CHIUSO_PMA_NO_BESAR", blocked: true },
    }));
  const open = (n: number) =>
    Array.from({ length: n }, () => ({
      baliL4: { status: "OK", blocked: false },
    }));

  it("names the non-moratorium codes instead of folding them into the risk tier", () => {
    // Guilt: this is the shape that was being misdescribed.
    const hint = baliBlockedHint([
      ...moratorium(407),
      ...scale(111),
      ...open(1041),
    ]);
    expect(hint).toContain("407");
    expect(hint).toContain("111");
    expect(hint).toContain("518 of 1559");
    // and it must NOT present the risk tier as the reason for all of them
    expect(hint).not.toMatch(
      /low and medium-low-risk activities are treated as closed/i,
    );
  });

  it("keeps the qualifier that made the original sentence honest", () => {
    // Innocence: the old copy's one virtue — it refused to pass as a legal
    // finding — must survive the rewrite. Losing it would be a regression
    // dressed as a correction.
    //
    // Case-INSENSITIVE on purpose. The first version of this assertion used
    // toContain("A working assessment"), which the old hardcoded sentence
    // failed on nothing but its lowercase "a" — i.e. it was asserting
    // capitalisation while claiming to assert substance, and it "caught" a
    // mutant that had the property it was testing for. Judge the entity, not
    // the form (superscar #3), especially in the assertion meant to protect
    // what must NOT change.
    const hint = baliBlockedHint([
      ...moratorium(407),
      ...scale(111),
      ...open(1041),
    ]);
    expect(hint).toMatch(
      /a working assessment, not a certified legal determination/i,
    );
  });

  it("does not invent a second cause when every block IS the moratorium", () => {
    // Innocence: the "the other N for a different reason" clause must not fire
    // on a population where it would be false.
    const hint = baliBlockedHint([...moratorium(50), ...open(50)]);
    expect(hint).toContain("all of them");
    expect(hint).not.toMatch(/for a different reason/i);
  });

  it("derives the counts from the data it is given, not from a frozen constant", () => {
    // The original went wrong by stating a rule in prose that the data later
    // contradicted. Two different populations must produce two different
    // sentences (W106: a constant is a measurement that stopped being taken).
    const a = baliBlockedHint([...moratorium(10), ...scale(5), ...open(85)]);
    const b = baliBlockedHint([...moratorium(20), ...scale(1), ...open(79)]);
    expect(a).not.toEqual(b);
    expect(a).toContain("15 of 100");
    expect(b).toContain("21 of 100");
  });

  it("never enumerates the non-moratorium causes, because an enumeration goes stale", () => {
    // The defect an adversarial review caught before ship: the first version
    // listed "an ownership restriction ... no Usaha Besar scale row, or a
    // sector regulator's own closure" — three of the FIVE statuses that occur,
    // silently dropping CHIUSO_BALI (70209) and CHIUSO_BALI_PROPOSTO (79110).
    // A new claim written while correcting an old one, unverified (W113).
    //
    // Built from the REAL status census, not from one fabricated status, which
    // is why the original test suite could not have caught it.
    const census: Array<[string, number]> = [
      ["BLOCCATO_CLASSE_RISCHIO", 372],
      ["CHIUSO_MORATORIA_BALI", 35],
      ["TERTUTUP", 68],
      ["CHIUSO_PMA_NO_BESAR", 39],
      ["CHIUSO_REGOLATORE_SETTORIALE", 2],
      ["CHIUSO_BALI", 1],
      ["CHIUSO_BALI_PROPOSTO", 1],
    ];
    const codes = census.flatMap(([status, n]) =>
      Array.from({ length: n }, () => ({ baliL4: { status, blocked: true } })),
    );
    const hint = baliBlockedHint([...codes, ...open(1041)]);
    expect(hint).toContain("518 of 1559");
    expect(hint).toContain("407");
    expect(hint).toContain("111");
    // No partial cause list may appear — naming some causes implies the set is
    // complete, and it never is for long.
    expect(hint).not.toMatch(/ownership restriction/i);
    expect(hint).not.toMatch(/Usaha Besar scale row/i);
    expect(hint).not.toMatch(/sector regulator/i);
  });

  it("says nothing at all rather than '0 of 0' when handed no codes", () => {
    // Also from the same review: an empty array rendered "0 of 0 codes are
    // treated as closed ... all of them under the moratorium", which is not a
    // degraded sentence but a false one.
    expect(baliBlockedHint([])).toBe("");
  });

  it("agrees with the served dataset — 518 blocked, 98 not by the moratorium", () => {
    // Anchors the two figures to the real records rather than to my arithmetic,
    // so a future overlay change fails here instead of silently making the
    // card wrong again.
    //
    // 111 → 98 on 2026-08-03: thirteen of the codes that used to be blocked
    // "because OSS holds no Usaha Besar row" turned out to be blocked by the
    // moratorium instead, once each was adjudicated against Perpres 49/2021
    // Lampiran II. The blocked TOTAL is unchanged at 518 — nothing opened, the
    // causes were re-attributed — which is why that figure is asserted here
    // too and not only the one that moved.
    const codes = (
      rawData as {
        data: Array<{ l4_bali?: { status?: string; blocked?: boolean } }>;
      }
    ).data.map((r) => ({
      baliL4: r.l4_bali
        ? { status: r.l4_bali.status, blocked: r.l4_bali.blocked }
        : null,
    }));
    const hint = baliBlockedHint(codes);
    expect(hint).toContain("518 of 1559");
    // Both halves of the split, each with the words around it: a bare "98"
    // would also be satisfied by the digits of some unrelated figure the
    // sentence might gain later, which is how a pin stops pinning.
    expect(hint).toContain("420 of them");
    expect(hint).toContain("the other 98");
  });
});

// =============================================================================
// isNationalClosure — a national bar recorded in the Bali-scoped field
// =============================================================================

describe("isNationalClosure — the banner and the FAQ must not send a client to Jakarta", () => {
  // The two statuses whose recorded reason is national on EVERY member, read one
  // by one off the live catalogue: a sectoral regulator / State monopoly, and a
  // Perpres 49/2021 Lampiran II allocation to Koperasi/UMKM.
  const NATIONAL = ["CHIUSO_REGOLATORE_SETTORIALE", "CHIUSO_PMA_NO_BESAR"];
  // Everything else `l4_bali` can carry while blocked. These are Bali-scoped (or
  // mixed, in TERTUTUP's case) and must keep the Bali framing.
  const BALI_SCOPED = [
    "BLOCCATO_CLASSE_RISCHIO",
    "CHIUSO_MORATORIA_BALI",
    "CHIUSO_BALI",
    "CHIUSO_BALI_PROPOSTO",
    "TERTUTUP",
  ];

  it("GUILT: every live record carrying a national status is recognised", () => {
    const national = RECORDS.filter((r) =>
      NATIONAL.includes(r.l4_bali?.status ?? ""),
    );
    // Premise first: an empty set would make every assertion below vacuous.
    expect(national.length).toBeGreaterThan(0);
    for (const r of national) {
      expect(isNationalClosure(r.l4_bali?.status)).toBe(true);
    }
    // The shape that fooled the old derivation was: a national cause recorded
    // in the Bali field while the NATIONAL signals still read wide open. That
    // used to be all nine. On 2026-08-06 the Lampiran II re-adjudication fixed
    // exactly one of them at the source — 95291 now reads TERBATAS/0 — so the
    // property is no longer universal, and asserting it as universal would make
    // this test fail every time the catalogue gets MORE honest.
    //
    // What is pinned instead is the size of the remaining contradiction. It may
    // only shrink: a new member means a code gained a national cause in the
    // Bali field while still publishing 100%, which is the bug this file is
    // about.
    //
    // 8 -> 5 on 2026-08-06: the split-heir cure fixed three more at the source
    // (96210, 96220, 96100), each of which had carried CHIUSO_PMA_NO_BESAR
    // while publishing 100%.
    //
    // The five that remain are NAMED below and not merely counted, because a
    // population with only a size cannot be closed by the pass that comes for
    // it — and these five are not one population at all:
    //
    //   64110 (Bank Indonesia) and 38122 (radioactive-waste collection) are
    //     CHIUSO_REGOLATORE_SETTORIALE — shut by their own sector's regulator,
    //     nothing to do with Lampiran II. They need their own adjudication and
    //     have never had one. Writing them down here is the point: they have
    //     been sitting inside an aggregate labelled "the remaining
    //     contradiction" and would have left it only by accident.
    //
    //   55201 (homestay), 55203 (villa) and 79903 (tour guide) are the vintage
    //     carries, adjudicated 2026-08-06 across two model families. 55203 is
    //     due to be cured (three seats, two families, all SAME); 55201 and
    //     79903 stay open on purpose — a cross-family seat withheld on 55201
    //     because settling it needs the KBLI-2020 text for "Pondok Wisata",
    //     which we do not hold, and 79903's own 2025 description adds
    //     coordinating freelance guides for travel agencies, which the annex
    //     row "Jasa pramuwisata" does not name.
    const stillContradictory = national.filter(
      (r) => r.pma_status === "TERBUKA" && r.pma_max_asing === 100,
    );
    expect(stillContradictory.length).toBe(5);
    expect(stillContradictory.map((r) => r.kode_kbli_2025).sort()).toEqual([
      "38122",
      "55201",
      "55203",
      "64110",
      "79903",
    ]);
    expect(national.map((r) => r.kode_kbli_2025)).toContain("95291");
    expect(stillContradictory.map((r) => r.kode_kbli_2025)).not.toContain(
      "95291",
    );
  });

  it("INNOCENCE: no Bali-scoped block is turned into a national one", () => {
    const baliScoped = BLOCKED.filter(
      (r) =>
        BALI_SCOPED.includes(r.l4_bali?.status ?? "") &&
        // The 8 per-code adjudications ARE national and are supposed to be
        // caught; excluding them keeps this test about the STATUS rule instead
        // of quietly re-testing the code list.
        nationalClosureBasis(r.kode_kbli_2025) === null,
    );
    // This is the set that would silently lose its Bali framing if the rule were
    // widened by "closed-sounding status" instead of by named entity.
    expect(baliScoped.length).toBeGreaterThan(100);
    const misclassified = baliScoped.filter((r) =>
      isNationalClosure(r.l4_bali?.status, r.kode_kbli_2025),
    );
    expect(misclassified.map((r) => r.kode_kbli_2025)).toEqual([]);
  });

  it("GUILT: the 8 per-code TERTUTUP adjudications each name their instrument", () => {
    // A code list is data wearing code's clothes, so it earns its keep only if
    // every entry stays auditable: the code must still be TERTUTUP on the live
    // catalogue (otherwise the adjudication is stale and nobody would know) and
    // must carry a stated basis. Read one by one — UU 18/2003 for advocates, UU
    // 30/2004 for notaries, Kemenkes health law for solo practice, the WNI
    // retail reservation, and the two national TERTUTUP/0% entries.
    const adjudicated = [
      "01287",
      "47111",
      "47112",
      "59131",
      "69102",
      "69104",
      "86201",
      "86202",
    ];
    for (const code of adjudicated) {
      const record = RECORDS.find((r) => r.kode_kbli_2025 === code);
      expect(record, `${code} left the catalogue`).toBeDefined();
      expect(record!.l4_bali?.status, `${code} is no longer TERTUTUP`).toBe(
        "TERTUTUP",
      );
      expect(nationalClosureBasis(code)).toBeTruthy();
      expect(isNationalClosure(record!.l4_bali?.status, code)).toBe(true);
    }
  });

  it("DECLARED GAP: the other TERTUTUP records never state a scope at all", () => {
    // The 68 split into 8 with a national legal basis, 2 that say "in Bali", and
    // 58 whose reason is "medium-high/high risk -> not blocked by moratorium
    // (verify per address)" — a sentence answering whether the MORATORIUM TEST
    // fired, never where the closure applies. The record does not hold the fact,
    // so no rule over `l4_bali` can invent it; those keep the Bali framing,
    // which understates rather than misdirects.
    // If this goes red the reasons gained a scope — read them and adjudicate,
    // do not just delete the test.
    const tertutup = RECORDS.filter((r) => r.l4_bali?.status === "TERTUTUP");
    expect(tertutup.length).toBeGreaterThan(1);
    const unscoped = tertutup.filter(
      (r) =>
        nationalClosureBasis(r.kode_kbli_2025) === null &&
        /not\s+blocked\s+by\s+moratorium/i.test(r.l4_bali?.reason ?? ""),
    );
    expect(unscoped.length).toBeGreaterThan(20);
    for (const r of unscoped) {
      expect(isNationalClosure(r.l4_bali?.status, r.kode_kbli_2025)).toBe(
        false,
      );
    }
    // …and the status ALONE still never nationalises anything.
    expect(isNationalClosure("TERTUTUP")).toBe(false);
  });

  it("an unknown or absent status is never treated as national", () => {
    for (const s of [
      undefined,
      null,
      "",
      "OK_or_HIGHER_RISK",
      "SOMETHING_NEW",
    ]) {
      expect(isNationalClosure(s)).toBe(false);
    }
  });
});

describe("the FAQ answer for a national closure", () => {
  it("GUILT: it never tells the reader the activity is open outside Bali", () => {
    const national = RECORDS.filter((r) =>
      ["CHIUSO_REGOLATORE_SETTORIALE", "CHIUSO_PMA_NO_BESAR"].includes(
        r.l4_bali?.status ?? "",
      ),
    );
    expect(national.length).toBeGreaterThan(0);
    // …plus the per-code adjudications, whose headline case is the notary page
    // that started this whole lane.
    const byCode = RECORDS.filter(
      (r) => nationalClosureBasis(r.kode_kbli_2025) !== null,
    );
    expect(byCode.map((r) => r.kode_kbli_2025)).toContain("69104");
    // Split by BRANCH, because only the `pma.status === "open"` records ever
    // reached the defective answer. Measured on the live catalogue: of the 8
    // per-code adjudications, 3 (`01287`, `59131` TERTUTUP/0 and `47111`
    // TERBATAS/0) were ALREADY answered correctly off `pma_status`, and 5
    // (`47112`, `69102`, `69104`, `86201`, `86202`) carry TERBUKA/100 — the
    // absence-from-the-annex default — and are what this rule actually changes.
    // They stay in the list regardless: the point is to stop depending on a
    // default fill that can move underneath us.
    let declaredGaps = 0;
    for (const r of [...national, ...byCode]) {
      const answer = buildKbliFaq(toKbliCodeForFaq(r))[0].answer.toLowerCase();
      // No branch, ever, may route the reader to another province.
      expect(answer, r.kode_kbli_2025).not.toContain("outside bali it is open");
      expect(answer, r.kode_kbli_2025).not.toContain("nationally yes");
      if (r.pma_status === "TERBUKA" && (r.pma_max_asing ?? 0) > 0) {
        if (
          r.pma_verification_status === "located" &&
          r.pma_official_basis &&
          r.pma_source_vintage
        ) {
          expect(answer, r.kode_kbli_2025).toContain("everywhere in indonesia");
        } else {
          expect(answer, r.kode_kbli_2025).toContain("not yet verified");
          expect(answer, r.kode_kbli_2025).not.toContain(
            "everywhere in indonesia",
          );
          declaredGaps += 1;
        }
      }
    }
    // The raw-open/default-filled national-closure stratum currently consists
    // only of declared gaps. The located innocence arm is covered separately;
    // here we pin that the gap never borrows certainty from the Bali layer.
    expect(declaredGaps).toBeGreaterThan(0);
  });

  it("INNOCENCE: a located Bali-only block keeps the 'nationally yes' answer", () => {
    const baliOnly = BLOCKED.filter(
      (r) => r.l4_bali?.status === "CHIUSO_MORATORIA_BALI",
    );
    expect(baliOnly.length).toBeGreaterThan(0);
    const base = toKbliCodeForFaq(baliOnly[0]);
    // The current canonical has no located member in this stratum. Promote one
    // synthetic copy with all three affirmative fields so the innocence arm
    // remains constrained without weakening the real-data gap expectation.
    const located: KBLICode = {
      ...base,
      pma: {
        ...base.pma,
        verificationStatus: "located",
        officialBasis: "Perpres fixture locator",
        sourceVintage: "2021-05-25",
      },
      provenance: {
        ...base.provenance!,
        pma: {
          source: base.pma.source,
          status: "located",
          locator: "Perpres fixture locator",
          vintage: "2021-05-25",
        },
      },
    };
    const answer = buildKbliFaq(located)[0].answer;
    expect(answer).toContain("Nationally yes");
  });
});

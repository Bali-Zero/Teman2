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
} from "./kbli-bali-block";
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";
import goldData from "../../data/kbli-gold-all.json";

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
  pma_cap_special?: boolean;
}
const RECORDS = (rawData as { data: RawRecord[] }).data;
const BLOCKED = RECORDS.filter((r) => r.l4_bali?.blocked === true);
const GOLD = goldData as unknown as Record<string, { whatYouNeed?: string }>;

const MORATORIUM_SENTENCE = "under the 13 May 2026 moratorium";

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

  it("pins the live population: 8 of the 44 zero-row gold pages", () => {
    // (see the PMA-verdict-banner block below for the second render site)
    // Measured on the canonical + gold of 2026-07-27. Pinned so that widening
    // or narrowing the frame is a visible, deliberate change rather than a
    // silent one — the same discipline as the untraceable-PMA pin.
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
    expect(framed.map((r) => r.kode_kbli_2025).sort()).toEqual([
      "72101",
      "75001",
      "75002",
      "75009",
      "86109",
      "86202",
      "86203",
      "91222",
    ]);
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
    expect(notice.length).toBe(455);
    expect(msme.length).toBe(7);
    // 448 pages carry the notice for a cause other than an MSME reservation.
    expect(notice.length - msme.length).toBe(448);
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
    expect(blocked.length - excluded.length).toBe(455);
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
    // Mirrors the builder's own guard: pma.status === "open" && baliL4.blocked,
    // where mapPmaStatus treats anything but TERBATAS/TERTUTUP as open.
    const openNationally = (r: RawRecord) => {
      const s = (r.pma_status ?? "").toUpperCase();
      return s !== "TERBATAS" && s !== "TERTUTUP";
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
    expect(answers.length).toBe(454);
    expect(msme.length).toBe(7);
    // 447 answers carry the block for a cause other than an MSME reservation —
    // in the visible Q&A and in the FAQPage JSON-LD, the copy that leaves the
    // site.
    expect(answers.length - msme.length).toBe(447);
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

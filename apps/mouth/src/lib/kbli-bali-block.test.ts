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

  it("pins the population: 456 render the notice, only 39 are MSME-reserved", () => {
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
    expect(notice.length).toBe(456);
    expect(msme.length).toBe(39);
    // 417 pages were being told a cause that was not theirs — 5.8x the
    // licensing-frame defect, and above the fold rather than deep in the page.
    expect(notice.length - msme.length).toBe(417);
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

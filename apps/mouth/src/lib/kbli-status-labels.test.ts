import { describe, expect, it } from "vitest";

import {
  BALI_STATUS_CONFIG,
  INTERNAL_ENUM_LABELS,
  humanizeInternalEnums,
  humanizeIntelBlock,
  humanizeStatValue,
} from "./kbli-status-labels";

/**
 * GUILT + INNOCENCE, per cicatrix superscar #3: a guard that only proves it
 * fires is half a guard. Every "it resolves X" here has a sibling proving it
 * leaves the neighbouring legitimate string alone.
 */
describe("humanizeStatValue — structured cells", () => {
  // ---- GUILT: the symbols that actually reached readers -------------------
  it("resolves the symbol that leaked onto 908 By-the-numbers cells", () => {
    expect(humanizeStatValue("OK_or_HIGHER_RISK")).toBe("Registrable in Bali");
  });

  it("resolves every Bali symbol that is not a term of art", () => {
    expect(humanizeStatValue("CHIUSO_MORATORIA_BALI")).toBe(
      "Closed in Bali (2026 moratorium)",
    );
    expect(humanizeStatValue("BLOCCATO_CLASSE_RISCHIO")).toBe(
      "Blocked in Bali (risk-class moratorium)",
    );
    expect(humanizeStatValue("NON_CLASSIFICABILE")).toBe(
      "Bali status not classifiable — verify",
    );
    expect(humanizeStatValue("CHIUSO_PMA_NO_BESAR")).toBe(
      "Reserved for MSME — closed to PT PMA",
    );
  });

  it("resolves the crosswalk symbols to the TransitionBadge wording", () => {
    expect(humanizeStatValue("BPS_ONLY")).toBe("New in 2025");
    expect(humanizeStatValue("MATCH_LANGSUNG")).toBe("Direct Match");
    expect(humanizeStatValue("CODICE_RINUMERATO")).toBe("Renumbered");
    expect(humanizeStatValue("MATCH_CON_AGGREGAZIONE")).toBe("Aggregated");
  });

  it("tolerates surrounding whitespace on a structured cell", () => {
    expect(humanizeStatValue("  OK_or_HIGHER_RISK ")).toBe(
      "Registrable in Bali",
    );
  });

  // ---- INNOCENCE: what must survive untouched -----------------------------
  it("leaves the Indonesian terms of art alone — they are the product's vocabulary", () => {
    expect(humanizeStatValue("TERBUKA")).toBe("TERBUKA");
    expect(humanizeStatValue("TERTUTUP")).toBe("TERTUTUP");
    expect(humanizeStatValue("TERBATAS")).toBe("TERBATAS");
  });

  it("never translates TERBUKA's siblings asymmetrically", () => {
    // The three terms travel together in the annexes; humanising only the
    // negative ones would make the same sidebar bilingual with itself.
    const terms = ["TERBUKA", "TERTUTUP", "TERBATAS"];
    for (const t of terms) expect(humanizeStatValue(t)).toBe(t);
  });

  it("leaves ordinary editorial cell values byte-identical", () => {
    for (const v of [
      "100%",
      "Perpres 10/2021, 49/2021",
      "Rp 2.5 billion",
      "Menengah Tinggi",
      "None retrievable (404)",
      "",
    ]) {
      expect(humanizeStatValue(v)).toBe(v);
    }
  });

  it("does not resolve an unknown symbol by guessing a near neighbour", () => {
    expect(humanizeStatValue("OK_or_LOWER_RISK")).toBe("OK_or_LOWER_RISK");
    expect(humanizeStatValue("BPS_ONLY_2020")).toBe("BPS_ONLY_2020");
    expect(humanizeStatValue("ok_or_higher_risk")).toBe("ok_or_higher_risk");
  });
});

describe("humanizeInternalEnums — prose", () => {
  // ---- GUILT --------------------------------------------------------------
  it("resolves the symbol inside a real editorial sentence", () => {
    expect(
      humanizeInternalEnums(
        "Its Bali status is OK_or_HIGHER_RISK, with the reason given that OSS risk at Besar scale is high.",
      ),
    ).toBe(
      "Its Bali status is Registrable in Bali, with the reason given that OSS risk at Besar scale is high.",
    );
  });

  it("resolves a symbol wrapped in markdown inline code", () => {
    expect(
      humanizeInternalEnums("the Bali status is `OK_or_HIGHER_RISK`"),
    ).toBe("the Bali status is `Registrable in Bali`");
  });

  it("resolves several symbols in one passage", () => {
    expect(
      humanizeInternalEnums("mapping BPS_ONLY, Bali OK_or_HIGHER_RISK."),
    ).toBe("mapping New in 2025, Bali Registrable in Bali.");
  });

  // ---- INNOCENCE ----------------------------------------------------------
  it("does not let a shorter symbol eat a longer one that shares its prefix", () => {
    // TERTUTUP is a term of art (never rewritten) and TERTUTUP_CANDIDATE is a
    // symbol; a naive substring pass would emit "Closed to foreigners_CANDIDATE".
    expect(humanizeInternalEnums("status TERTUTUP_CANDIDATE here")).toBe(
      "status Likely closed — verify here",
    );
    expect(humanizeInternalEnums("status TERBATAS_CANDIDATE here")).toBe(
      "status Likely restricted — verify here",
    );
  });

  it("does not fire on a symbol glued into a longer identifier", () => {
    expect(
      humanizeInternalEnums("XBPS_ONLY and BPS_ONLYX and BPS_ONLY_V2"),
    ).toBe("XBPS_ONLY and BPS_ONLYX and BPS_ONLY_V2");
  });

  it("leaves prose with no internal symbol byte-identical", () => {
    const prose =
      "KBLI 68112 is TERBUKA — open to 100% foreign ownership via PT PMA. " +
      "The Bali moratorium blocks Low and Medium-Low risk activities island-wide.";
    expect(humanizeInternalEnums(prose)).toBe(prose);
  });

  it("is idempotent — a label carries no symbol to resolve again", () => {
    const once = humanizeInternalEnums("Bali status is OK_or_HIGHER_RISK.");
    expect(humanizeInternalEnums(once)).toBe(once);
  });

  it("passes an empty string through", () => {
    expect(humanizeInternalEnums("")).toBe("");
  });
});

describe("humanizeIntelBlock — the loader choke point", () => {
  it("cleans prose fields, editorial prose and byTheNumbers cells at once", () => {
    const out = humanizeIntelBlock({
      whatChanged: "KBLI 2020→2025 mapping (BPS_ONLY).",
      whatYouNeed: "Bali: OK_or_HIGHER_RISK.",
      baliContext: null,
      coverImage: "/covers/x.png",
      editorial: {
        headline: "A carbon code with no OSS scope",
        standfirst: "Bali reads OK_or_HIGHER_RISK.",
        body: "The record says the Bali status is OK_or_HIGHER_RISK.",
        pullQuote: "Marked OK_or_HIGHER_RISK.",
        byTheNumbers: [
          { label: "Bali status", value: "OK_or_HIGHER_RISK" },
          { label: "National status", value: "TERBUKA" },
          { label: "Ceiling", value: "100%" },
        ],
      },
    });

    expect(out.whatChanged).toBe("KBLI 2020→2025 mapping (New in 2025).");
    expect(out.whatYouNeed).toBe("Bali: Registrable in Bali.");
    expect(out.editorial.standfirst).toBe("Bali reads Registrable in Bali.");
    expect(out.editorial.body).toBe(
      "The record says the Bali status is Registrable in Bali.",
    );
    expect(out.editorial.pullQuote).toBe("Marked Registrable in Bali.");
    expect(out.editorial.byTheNumbers).toEqual([
      { label: "Bali status", value: "Registrable in Bali" },
      { label: "National status", value: "TERBUKA" },
      { label: "Ceiling", value: "100%" },
    ]);
  });

  it("preserves non-string members and unknown keys, and never mutates its input", () => {
    const input = {
      whatChanged: "Bali OK_or_HIGHER_RISK.",
      baliContext: null,
      coverImage: "/covers/x.png",
      someFutureKey: { nested: true },
    };
    const snapshot = JSON.stringify(input);
    const out = humanizeIntelBlock(input);

    expect(JSON.stringify(input)).toBe(snapshot); // input untouched
    expect(out.baliContext).toBeNull();
    expect(out.coverImage).toBe("/covers/x.png");
    expect(out.someFutureKey).toEqual({ nested: true });
    expect(out).not.toBe(input);
  });

  it("covers fields no allow list mentioned — whoThisIsFor and nested tkaInfo", () => {
    // The regression this test exists for: `whoThisIsFor` (1,186 records,
    // rendered on the code page) and `tkaInfo.insight` were invisible to the
    // first, allow-list-based version of the cure.
    const out = humanizeIntelBlock({
      whoThisIsFor: "Founders whose Bali status reads OK_or_HIGHER_RISK.",
      tkaInfo: {
        insight: "Mapping is BPS_ONLY.",
        relevantPositions: ["Director — BLOCCATO_CLASSE_RISCHIO note"],
      },
      aFieldInventedTomorrow: "Bali OK_or_HIGHER_RISK.",
    });

    expect(out.whoThisIsFor).toBe(
      "Founders whose Bali status reads Registrable in Bali.",
    );
    expect(out.tkaInfo.insight).toBe("Mapping is New in 2025.");
    expect(out.tkaInfo.relevantPositions).toEqual([
      "Director — Blocked in Bali (risk-class moratorium) note",
    ]);
    expect(out.aFieldInventedTomorrow).toBe("Bali Registrable in Bali.");
  });

  it("INNOCENCE: leaves machine-metadata keys byte-identical", () => {
    // `_l3_regen` records WHAT the pipeline did; a symbol there is a fact about
    // the run, not a sentence aimed at a reader. Rewriting it falsifies the
    // regeneration audit trail. `coverImage` is an asset path.
    const out = humanizeIntelBlock({
      _l3_regen: {
        model: "sonnet",
        note: "regenerated from OK_or_HIGHER_RISK branch",
        fact_gate: "BPS_ONLY",
      },
      coverImage: "/covers/OK_or_HIGHER_RISK.png",
      whatItMeans: "Bali OK_or_HIGHER_RISK.",
    });

    expect(out._l3_regen).toEqual({
      model: "sonnet",
      note: "regenerated from OK_or_HIGHER_RISK branch",
      fact_gate: "BPS_ONLY",
    });
    expect(out.coverImage).toBe("/covers/OK_or_HIGHER_RISK.png");
    expect(out.whatItMeans).toBe("Bali Registrable in Bali."); // still cured
  });

  it("passes undefined / null / non-objects straight through", () => {
    expect(humanizeIntelBlock(undefined)).toBeUndefined();
    expect(humanizeIntelBlock(null)).toBeNull();
    expect(humanizeIntelBlock("string")).toBe("string");
  });

  it("survives an editorial with no byTheNumbers", () => {
    const out = humanizeIntelBlock({
      editorial: { headline: "H", body: "Bali OK_or_HIGHER_RISK." } as Record<
        string,
        unknown
      >,
    });
    expect(out.editorial.body).toBe("Bali Registrable in Bali.");
    expect(out.editorial.byTheNumbers).toBeUndefined();
  });
});

describe("map integrity", () => {
  it("keeps the badge table and the humaniser in lockstep", () => {
    // A status the badge can render but the humaniser cannot resolve would put
    // two different words for one verdict on the same page.
    const TERMS_OF_ART = new Set(["TERBUKA", "TERTUTUP", "TERBATAS"]);
    for (const [key, cfg] of Object.entries(BALI_STATUS_CONFIG)) {
      if (TERMS_OF_ART.has(key)) {
        expect(INTERNAL_ENUM_LABELS[key]).toBeUndefined();
      } else {
        expect(INTERNAL_ENUM_LABELS[key]).toBe(cfg.label);
      }
    }
  });

  it("never maps a symbol to something that still looks like a symbol", () => {
    for (const label of Object.values(INTERNAL_ENUM_LABELS)) {
      expect(label).not.toMatch(/^[A-Z][A-Za-z]*(_[A-Za-z]+)+$/);
    }
  });
});

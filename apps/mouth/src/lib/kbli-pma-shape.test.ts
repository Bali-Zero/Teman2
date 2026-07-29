// Corpus for the ownership-cap extremes.
//
// GUILT is the three strings that were LIVE on balizero.com on 2026-07-29:
//   /kbli/47111  "Max 0% Foreign Ownership"                       (cap 0)
//   /kbli/79110  "Max 100% Foreign Ownership"                     (cap 100)
//   /kbli/47221  "Restricted to max special% foreign ownership"   (cap "special")
// INNOCENCE is the seven codes that were always right (cap 49) plus the
// provenance gate: an UNVERIFIED cap must still refuse to state a figure, and
// that refusal must not be re-opened by any of the branches added here.
//
// The reason this file exists at all: kbli-meta.test.ts exercised the cap with
// 100 (on an `open` code) and 67 — the middle of the range and nothing else, so
// the formula was proven exactly where it was already correct.

import { describe, expect, it } from "vitest";
import type { KBLICode } from "./kbli-types";
import { pmaCapShape, restrictedCapBadge } from "./kbli-pma-shape";
import { kbliMetaTitleSuffix, kbliPmaLabel } from "./kbli-meta";
import { buildKbliFaq } from "./kbli-faq";

function restricted(overrides: Partial<KBLICode["pma"]> = {}): KBLICode {
  return {
    code: "47111",
    titleId: "Perdagangan Eceran Swalayan",
    titleEn: "Supermarket / Hypermarket",
    titleEnMeta: "Supermarket / Hypermarket",
    description: "Test description",
    section: "G",
    sectionName: "Wholesale and Retail Trade",
    pma: {
      status: "restricted",
      maxForeign: 49,
      condition: null,
      isPriority: false,
      note: null,
      source: "Perpres 10/2021",
      capSpecial: false,
      capVerified: true,
      routeTo: null,
      ...overrides,
    },
    licensing: [],
    transition: {
      mappingStatus: "MATCH_LANGSUNG",
      previousCodes: [],
      kbli2020Source: null,
      mappingNote: null,
      aggregationNote: null,
    },
    tier: "silver",
    keywords: [],
  } as unknown as KBLICode;
}

const pmaAnswerOf = (code: KBLICode) =>
  buildKbliFaq(code).find((q) => /foreign|PMA|own/i.test(q.question))?.answer ??
  "";

describe("pmaCapShape", () => {
  it("classifies the middle of the range as a real percentage", () => {
    expect(pmaCapShape(restricted({ maxForeign: 49 }).pma)).toBe("partial");
    expect(pmaCapShape(restricted({ maxForeign: 1 }).pma)).toBe("partial");
    expect(pmaCapShape(restricted({ maxForeign: 99 }).pma)).toBe("partial");
  });

  it("treats both extremes as NOT a percentage", () => {
    expect(pmaCapShape(restricted({ maxForeign: 0 }).pma)).toBe("none");
    expect(pmaCapShape(restricted({ maxForeign: 100 }).pma)).toBe("full");
  });

  it("treats a non-numeric cap as conditional even when the flag disagrees", () => {
    // `capSpecial` and the "special" cap value come from two INDEPENDENT raw
    // fields (pma_cap_special / pma_max_asing). They agree on exactly one
    // record today; nothing structural keeps them in step, and this arm is what
    // stops a literal "Max special%" if they ever drift apart.
    expect(
      pmaCapShape(restricted({ maxForeign: "special", capSpecial: false }).pma),
    ).toBe("conditional");
  });
});

describe("the <title> suffix", () => {
  it("GUILT: a 0% ceiling is not a share on offer", () => {
    const suffix = kbliMetaTitleSuffix(restricted({ maxForeign: 0 }));
    expect(suffix).not.toContain("Max 0%");
    expect(suffix).toBe("Closed to Foreign Investment");
  });

  it("GUILT: a 100% ceiling restricts nothing", () => {
    const suffix = kbliMetaTitleSuffix(restricted({ maxForeign: 100 }));
    expect(suffix).not.toContain("Max 100%");
    expect(suffix).toBe("Foreign Ownership With Conditions");
  });

  it("GUILT: a drifted non-numeric cap never reaches the page as a number", () => {
    const suffix = kbliMetaTitleSuffix(
      restricted({ maxForeign: "special", capSpecial: false }),
    );
    expect(suffix).not.toContain("special%");
    expect(suffix).not.toMatch(/Max /);
  });

  it("INNOCENCE: the seven cap-49 codes are untouched", () => {
    expect(kbliMetaTitleSuffix(restricted({ maxForeign: 49 }))).toBe(
      "Max 49% Foreign Ownership",
    );
  });

  it("INNOCENCE: the capSpecial regime keeps its own wording", () => {
    expect(
      kbliMetaTitleSuffix(
        restricted({ maxForeign: "special", capSpecial: true }),
      ),
    ).toBe("Foreign Ownership With Conditions");
  });

  it("INNOCENCE: an unverified cap still states nothing — at ANY shape", () => {
    // The provenance gate predates this change and must survive it. If a future
    // edit reorders the branches so a shape answers before capVerified, an
    // unverified 0 would start asserting "Closed to Foreign Investment" as fact.
    for (const cap of [0, 49, 100] as const) {
      expect(
        kbliMetaTitleSuffix(
          restricted({ maxForeign: cap, capVerified: false }),
        ),
      ).toBe("Foreign Ownership Restricted");
    }
  });
});

describe("the <meta description> label", () => {
  it("GUILT: degrades at both extremes instead of printing them", () => {
    expect(kbliPmaLabel(restricted({ maxForeign: 0 }))).toBe(
      "Closed to Foreign Investment",
    );
    expect(kbliPmaLabel(restricted({ maxForeign: 100 }))).not.toContain(
      "max 100%",
    );
  });

  it("INNOCENCE: still prints a genuine ceiling, and still hides an unverified one", () => {
    expect(kbliPmaLabel(restricted({ maxForeign: 49 }))).toBe(
      "Restricted (max 49% foreign)",
    );
    expect(
      kbliPmaLabel(restricted({ maxForeign: 49, capVerified: false })),
    ).toBe("Restricted for foreign ownership");
  });
});

describe("the FAQ answer — visible copy AND FAQPage JSON-LD", () => {
  it("GUILT: at 100% there are no remaining shares for a partner to hold", () => {
    const answer = pmaAnswerOf(restricted({ maxForeign: 100 }));
    expect(answer).not.toContain("remaining shares");
    expect(answer).not.toContain("capped at 100%");
  });

  it("GUILT: at 0% the answer is no, not a cap", () => {
    const answer = pmaAnswerOf(restricted({ maxForeign: 0 }));
    expect(answer).not.toContain("capped at 0%");
    expect(answer).not.toContain("remaining shares");
    expect(answer.startsWith("No.")).toBe(true);
  });

  it("INNOCENCE: a real ceiling keeps the partner clause that is true for it", () => {
    const answer = pmaAnswerOf(restricted({ maxForeign: 49 }));
    expect(answer).toContain("capped at 49%");
    expect(answer).toContain(
      "An Indonesian partner holds the remaining shares",
    );
  });

  it("splices the condition as its own sentence", () => {
    // Live on /kbli/47111 as "Condition: UMKM only An Indonesian partner…" —
    // the dataset's condition strings carry no terminal punctuation.
    const answer = pmaAnswerOf(
      restricted({ maxForeign: 49, condition: "UMKM only" }),
    );
    expect(answer).toContain("Condition: UMKM only.");
    expect(answer).not.toContain("UMKM only An");
  });

  it("does not double the punctuation when the condition already ends a sentence", () => {
    const answer = pmaAnswerOf(
      restricted({ maxForeign: 49, condition: "Kemitraan dengan UMKM." }),
    );
    expect(answer).toContain("Condition: Kemitraan dengan UMKM.");
    expect(answer).not.toContain("UMKM..");
  });
});

describe("the visible badge", () => {
  it("GUILT: never renders a percentage that is not one", () => {
    expect(restrictedCapBadge(restricted({ maxForeign: 0 }).pma)).toBe(
      "Closed (0%)",
    );
    expect(restrictedCapBadge(restricted({ maxForeign: 100 }).pma)).toBe(
      "Conditions apply",
    );
    expect(
      restrictedCapBadge(
        restricted({ maxForeign: "special", capSpecial: false }).pma,
      ),
    ).not.toContain("special%");
  });

  it("INNOCENCE: keeps the ceiling, and keeps the unverified qualifier", () => {
    expect(restrictedCapBadge(restricted({ maxForeign: 49 }).pma)).toBe(
      "Max 49%",
    );
    expect(
      restrictedCapBadge(
        restricted({ maxForeign: 49, capVerified: false }).pma,
      ),
    ).toBe("≈49% (unverified)");
  });
});

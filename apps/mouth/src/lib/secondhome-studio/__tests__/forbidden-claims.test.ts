import { describe, expect, it } from "vitest";

import { COPY } from "../copy";

/**
 * The e33_claim_guard forbidden-pattern list, verbatim from
 * SPEC-secondhome-studio-phaseB.md §6. Case-insensitive by design (the
 * spec calls this out explicitly) — every pattern below carries the `i`
 * flag.
 */
const FORBIDDEN_PATTERNS: Record<string, RegExp> = {
  priceUsd1500: /US?D?\s*\$?\s*1[,.]?500/i,
  anyBank: /any\s+(Indonesian\s+)?bank/i,
  e33SR: /E33[SR]\b/i,
  workLocallyOrInIndonesia: /work(ing)?\s+(locally|in\s+indonesia)/i,
  automaticItapOrPermanent: /automatic(ally)?\s+.*(ITAP|permanent)/i,
  fiveToTenYears: /5\s*[-–]\s*10\s*years?/i,
  idr2Million: /IDR\s*2[,.]?000[,.]?000\b/i,
  guaranteedOr100PercentApproval: /guarantee[ds]?\s+approval|100%\s+approval/i,
  lps: /\bLPS\b/i,
  bsiOrSharia: /\bBSI\b|sharia/i,
  splitDeposit: /split(ting)?\s+.*deposit/i,
};

/** No hardcoded IDR price literal anywhere — the figure renders only from
 *  usePricingData. Covers both the pre-repricing (39M) and current (35M)
 *  values so a future reprice can't silently reintroduce a stale one. */
const PRICE_LITERAL_PATTERN =
  /35[,.]?000[,.]?000|39[,.]?000[,.]?000|\b39M\b|\b35M\b/i;

interface CopyEntry {
  path: string;
  value: string;
}

function collectStrings(node: unknown, path: string, out: CopyEntry[]): void {
  if (typeof node === "string") {
    out.push({ path, value: node });
    return;
  }
  if (typeof node !== "object" || node === null) return;
  for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
    collectStrings(value, path ? `${path}.${key}` : key, out);
  }
}

function allCopyStrings(): CopyEntry[] {
  const out: CopyEntry[] = [];
  collectStrings(COPY, "", out);
  return out;
}

// Hoisted to module scope so every describe block below shares one walk of
// the (large, deck-sourced) COPY tree.
const entries = allCopyStrings();

describe("forbidden-claims sweep — every string in COPY", () => {
  it("the sweep actually walks a non-trivial number of strings (guards against an empty/broken walk)", () => {
    expect(entries.length).toBeGreaterThan(40);
  });

  it.each(Object.entries(FORBIDDEN_PATTERNS))(
    "no copy string matches the %s pattern",
    (name, pattern) => {
      const violations = entries.filter((e) => pattern.test(e.value));
      expect(
        violations,
        `pattern "${name}" matched: ${violations.map((v) => v.path).join(", ")}`,
      ).toEqual([]);
    },
  );

  it("no copy string contains a hardcoded price literal (35M/39M in any form)", () => {
    const violations = entries.filter((e) =>
      PRICE_LITERAL_PATTERN.test(e.value),
    );
    expect(
      violations,
      `price literal leaked in: ${violations.map((v) => v.path).join(", ")}`,
    ).toEqual([]);
  });
});

describe("guilt fixtures — each pattern actually fires on a known-bad string", () => {
  const guiltCases: Array<{
    pattern: keyof typeof FORBIDDEN_PATTERNS;
    text: string;
  }> = [
    {
      pattern: "priceUsd1500",
      text: "The total cost is USD 1,500 for processing.",
    },
    { pattern: "priceUsd1500", text: "Just US$1500 flat." },
    { pattern: "anyBank", text: "You can open the account at any bank." },
    { pattern: "anyBank", text: "Works with any Indonesian bank." },
    { pattern: "e33SR", text: "Apply now for E33S." },
    { pattern: "e33SR", text: "The E33R variant is also available." },
    {
      pattern: "workLocallyOrInIndonesia",
      text: "This visa lets you work locally in Bali.",
    },
    {
      pattern: "workLocallyOrInIndonesia",
      text: "You are permitted to work in Indonesia.",
    },
    {
      pattern: "automaticItapOrPermanent",
      text: "Your KITAS automatically converts to ITAP after 3 years.",
    },
    {
      pattern: "automaticItapOrPermanent",
      text: "This status automatically becomes permanent residency.",
    },
    { pattern: "fiveToTenYears", text: "Valid for 5-10 years, typically." },
    { pattern: "fiveToTenYears", text: "Somewhere between 5 – 10 years." },
    {
      pattern: "idr2Million",
      text: "A processing fee of IDR 2,000,000 applies.",
    },
    {
      pattern: "guaranteedOr100PercentApproval",
      text: "We offer guaranteed approval for your visa.",
    },
    {
      pattern: "guaranteedOr100PercentApproval",
      text: "100% approval, no exceptions.",
    },
    {
      pattern: "lps",
      text: "Your deposit is protected by LPS deposit insurance.",
    },
    { pattern: "bsiOrSharia", text: "Also available via BSI." },
    {
      pattern: "bsiOrSharia",
      text: "A sharia-compliant deposit option exists.",
    },
    {
      pattern: "splitDeposit",
      text: "You may consider splitting your deposit across two accounts.",
    },
  ];

  it.each(guiltCases)("$pattern fires on: $text", ({ pattern, text }) => {
    expect(FORBIDDEN_PATTERNS[pattern].test(text)).toBe(true);
  });

  it("the price-literal pattern fires on known-bad price strings", () => {
    expect(PRICE_LITERAL_PATTERN.test("IDR 35,000,000")).toBe(true);
    expect(PRICE_LITERAL_PATTERN.test("IDR 39.000.000")).toBe(true);
    expect(PRICE_LITERAL_PATTERN.test("only 39M")).toBe(true);
    expect(PRICE_LITERAL_PATTERN.test("just 35M all-in")).toBe(true);
  });
});

describe("innocence pins — legitimate copy must NOT trip the guard (superscar #3 twin check)", () => {
  it('"non-working residency" does not trip the work-locally pattern', () => {
    expect(
      FORBIDDEN_PATTERNS.workLocallyOrInIndonesia.test("non-working residency"),
    ).toBe(false);
    expect(
      FORBIDDEN_PATTERNS.workLocallyOrInIndonesia.test(
        "This is a non-working residency permit.",
      ),
    ).toBe(false);
  });

  it("the actual copy module uses the safe 'non-working' framing somewhere and it passes the sweep", () => {
    const hasNonWorking = entries.some((e) => /non-working/i.test(e.value));
    // Not a hard requirement of this module (no copy currently needs to
    // describe work rights explicitly), but if it's ever added it must use
    // the safe phrasing — this pin documents and locks that in.
    if (hasNonWorking) {
      const offenders = entries.filter(
        (e) =>
          /non-working/i.test(e.value) &&
          FORBIDDEN_PATTERNS.workLocallyOrInIndonesia.test(e.value),
      );
      expect(offenders).toEqual([]);
    }
  });

  it("USD 130,000 (the real deposit figure) does not trip the USD 1,500 pattern", () => {
    expect(FORBIDDEN_PATTERNS.priceUsd1500.test("USD 130,000")).toBe(false);
  });

  it("USD 1,000,000 (the real property threshold) does not trip the USD 1,500 pattern", () => {
    expect(FORBIDDEN_PATTERNS.priceUsd1500.test("USD 1,000,000")).toBe(false);
  });

  it("E33E / E33F (real product codes) do not trip the E33S/E33R pattern", () => {
    expect(FORBIDDEN_PATTERNS.e33SR.test("E33E")).toBe(false);
    expect(FORBIDDEN_PATTERNS.e33SR.test("E33F")).toBe(false);
    expect(FORBIDDEN_PATTERNS.e33SR.test("the E33E senior pattern")).toBe(
      false,
    );
  });

  it("'up to 5 years, renewable (10-year cumulative cap)' does not trip the 5-10-years pattern", () => {
    expect(
      FORBIDDEN_PATTERNS.fiveToTenYears.test(
        "First grant up to 5 years, renewable (10-year cumulative cap, Pasal 113).",
      ),
    ).toBe(false);
  });

  it("the rewritten capital.why string (no literal 'split') does not trip splitDeposit", () => {
    // The copy deck's own draft here — "Split deposits do not qualify." —
    // DOES trip this pattern (proven below); copy.ts carries a reworded
    // version that keeps the same fact without the literal word "split".
    expect(FORBIDDEN_PATTERNS.splitDeposit.test(COPY.wizard.capital.why)).toBe(
      false,
    );
  });

  it("documents the deck's own draft phrasing WOULD have tripped splitDeposit (why the rewrite was needed)", () => {
    expect(
      FORBIDDEN_PATTERNS.splitDeposit.test(
        "The threshold must be met through one qualifying deposit. Split deposits do not qualify.",
      ),
    ).toBe(true);
  });
});

describe("positive pins — required phrasing is actually present", () => {
  it("custody copy contains 'state-owned' and 'own name'", () => {
    const custodyStrings = [
      COPY.custody.eyebrow,
      COPY.custody.intro,
      ...Object.values(COPY.custody.steps).map(
        (step) => `${step.title} ${step.body}`,
      ),
      COPY.custody.disclaimer,
    ]
      .join(" ")
      .toLowerCase();
    expect(custodyStrings).toContain("state-owned");
    expect(custodyStrings).toContain("own name");
  });

  it("custody step 3 keeps the withdrawal/compliance warning (copy-deck critique #2)", () => {
    const step3 = COPY.custody.steps.step3.body.toLowerCase();
    expect(step3).toMatch(/withdraw|moving them|move them/);
    expect(step3).toContain("compliance");
  });

  it("every verdict band body states the final decision rests with Imigrasi", () => {
    for (const band of Object.values(COPY.verdict.bands)) {
      expect(band.body.toLowerCase()).toContain(
        "the final decision rests with imigrasi",
      );
    }
  });

  it("dependents are described as priced in the free fit memo, never with a figure", () => {
    const dependentsNote = COPY.wizard.family.dependentsNote.toLowerCase();
    expect(dependentsNote).toContain("fit memo");
    expect(PRICE_LITERAL_PATTERN.test(dependentsNote)).toBe(false);
  });

  it("save-plan bar carries the deck's link warning and clear-plan action string", () => {
    expect(COPY.savePlanBar.linkWarning.toLowerCase()).toContain("link");
    expect(COPY.savePlanBar.linkWarning.toLowerCase()).toMatch(/view|see/);
    expect(COPY.savePlanBar.clearButton.toLowerCase()).toContain("clear");
  });

  it("whatsapp block carries the deck's privacy string (review-before-send)", () => {
    expect(COPY.whatsapp.privacy.toLowerCase()).toContain("review");
  });

  it("whatsapp prefill template names the fit-check result, never an assessment/certificate/score", () => {
    expect(COPY.whatsapp.prefillTemplate).toContain("Fit-check result:");
  });
});

describe("terminology delta — 'fit-check result' only, never assessment/certificate/eligibility score", () => {
  it("no copy string ever says 'assessment'", () => {
    const violations = entries.filter((e) => /assessment/i.test(e.value));
    expect(
      violations,
      `"assessment" found in: ${violations.map((v) => v.path).join(", ")}`,
    ).toEqual([]);
  });

  it("no copy string ever says 'certificate'", () => {
    const violations = entries.filter((e) => /certificate/i.test(e.value));
    expect(
      violations,
      `"certificate" found in: ${violations.map((v) => v.path).join(", ")}`,
    ).toEqual([]);
  });

  it("no copy string ever says 'eligibility score'", () => {
    const violations = entries.filter((e) =>
      /eligibility\s+score/i.test(e.value),
    );
    expect(
      violations,
      `"eligibility score" found in: ${violations.map((v) => v.path).join(", ")}`,
    ).toEqual([]);
  });

  it("'fit-check result' is actually used in the copy", () => {
    const hasPhrase = entries.some((e) => /fit-check result/i.test(e.value));
    expect(hasPhrase).toBe(true);
  });

  it("the deck's own draft ('a preliminary fit assessment') would have tripped the assessment ban (why the rewrite was needed)", () => {
    expect(
      /assessment/i.test(
        "This is a preliminary fit assessment, not an approval.",
      ),
    ).toBe(true);
  });
});

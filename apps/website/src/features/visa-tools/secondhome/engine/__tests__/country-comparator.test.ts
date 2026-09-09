import { describe, expect, it } from "vitest";

import {
  COUNTRY_PROGRAMMES,
  FAIRNESS_HIGHLIGHTS,
  MALAYSIA_MM2H_TIERS,
  PORTUGAL_D7_INCOME_FORMULA,
  type CountryProgramme,
  type SourcedCell,
} from "../country-comparator";

/**
 * Structural guards for the country-comparator DATA CONTRACT — these exist
 * so the mandate's hard exclusions are unfalsifiable, not a comment the
 * next contributor deletes. Guilt+innocence fixtures throughout, per
 * superscar #3 discipline (a guard proven only on today's clean data would
 * be an under-match twin waiting to happen).
 */

// ---------------------------------------------------------------------------
// Generic walkers — same shape as forbidden-claims.test.ts's collectStrings,
// plus a SourcedCell-aware variant for the provenance check.
// ---------------------------------------------------------------------------

interface StringEntry {
  path: string;
  value: string;
}

function collectStrings(node: unknown, path: string, out: StringEntry[]): void {
  if (typeof node === "string") {
    out.push({ path, value: node });
    return;
  }
  if (
    typeof node === "number" ||
    typeof node === "boolean" ||
    node === null ||
    node === undefined
  ) {
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((item, i) => collectStrings(item, `${path}[${i}]`, out));
    return;
  }
  if (typeof node === "object") {
    for (const [key, value] of Object.entries(
      node as Record<string, unknown>,
    )) {
      collectStrings(value, path ? `${path}.${key}` : key, out);
    }
  }
}

interface FoundCell {
  path: string;
  cell: SourcedCell<unknown>;
}

function isSourcedCellShape(node: unknown): node is SourcedCell<unknown> {
  if (typeof node !== "object" || node === null) return false;
  const n = node as Record<string, unknown>;
  return (
    "value" in n &&
    "sourceUrl" in n &&
    "capturedDate" in n &&
    "sourceLastUpdated" in n &&
    "confidence" in n
  );
}

function collectCells(node: unknown, path: string, out: FoundCell[]): void {
  if (isSourcedCellShape(node)) {
    out.push({ path, cell: node });
    return; // a cell's own fields (value/caveat) are not themselves cells
  }
  if (Array.isArray(node)) {
    node.forEach((item, i) => collectCells(item, `${path}[${i}]`, out));
    return;
  }
  if (typeof node === "object" && node !== null) {
    for (const [key, value] of Object.entries(
      node as Record<string, unknown>,
    )) {
      collectCells(value, path ? `${path}.${key}` : key, out);
    }
  }
}

const DATASET_ROOT = {
  COUNTRY_PROGRAMMES,
  MALAYSIA_MM2H_TIERS,
  PORTUGAL_D7_INCOME_FORMULA,
  FAIRNESS_HIGHLIGHTS,
};

/**
 * Provenance fields (`capturedDate`, `sourceLastUpdated`, `sourceUrl`) are
 * technical, not editorial content — an ISO date like "2026-08-24" is
 * digit-hyphen-digit and would otherwise false-positive against a
 * phone-number-shaped pattern. Content scans (forbidden claims, PII, price
 * literals) walk only the CONTENT strings; `findMissingProvenance` below
 * checks the technical fields directly against their own rules instead.
 */
const TECHNICAL_FIELD_SUFFIXES = [
  ".capturedDate",
  ".sourceLastUpdated",
  ".sourceUrl",
];
function isTechnicalField(path: string): boolean {
  return TECHNICAL_FIELD_SUFFIXES.some((suffix) => path.endsWith(suffix));
}

const allStringsRaw: StringEntry[] = [];
collectStrings(DATASET_ROOT, "", allStringsRaw);
const allStrings = allStringsRaw.filter((e) => !isTechnicalField(e.path));

const allCells: FoundCell[] = [];
collectCells(DATASET_ROOT, "root", allCells);

function stringsUnder(node: unknown, path: string): StringEntry[] {
  const out: StringEntry[] = [];
  collectStrings(node, path, out);
  return out.filter((e) => !isTechnicalField(e.path));
}

function programmesFor(country: string): readonly CountryProgramme[] {
  return COUNTRY_PROGRAMMES.filter((p) => p.country === country);
}

// ---------------------------------------------------------------------------
// Sanity — guards against an empty/broken walk before trusting any [] result
// below.
// ---------------------------------------------------------------------------

describe("sanity — the dataset actually has content to guard", () => {
  it("has 7 programmes across 5 countries", () => {
    expect(COUNTRY_PROGRAMMES.length).toBe(7);
    expect(new Set(COUNTRY_PROGRAMMES.map((p) => p.country)).size).toBe(5);
  });

  it("Malaysia has exactly 5 tiers", () => {
    expect(MALAYSIA_MM2H_TIERS.length).toBe(5);
  });

  it("Philippines contributes exactly one programme, SRRV Classic — no Smile row, no Courtesy row", () => {
    expect(programmesFor("Philippines").map((p) => p.id)).toEqual([
      "philippines_srrv_classic",
    ]);
  });

  it("the string walk finds a non-trivial number of strings", () => {
    expect(allStrings.length).toBeGreaterThan(50);
  });

  it("the cell walk finds a non-trivial number of SourcedCells", () => {
    expect(allCells.length).toBeGreaterThan(30);
  });

  it("the technical-field filter excludes date/URL fields but keeps content fields (guilt+innocence)", () => {
    expect(isTechnicalField("root.foo.capturedDate")).toBe(true);
    expect(isTechnicalField("root.foo.sourceLastUpdated")).toBe(true);
    expect(isTechnicalField("root.foo.sourceUrl")).toBe(true);
    expect(isTechnicalField("root.foo.value")).toBe(false);
    expect(isTechnicalField("root.foo.caveat")).toBe(false);
    // An ISO date would otherwise false-positive a phone-number-shaped
    // pattern — proves the filter actually removes what it claims to.
    expect(allStrings.some((e) => e.value === "2026-08-24")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Exclusion #1 — SRRV Smile never stated as a settled fact.
// ---------------------------------------------------------------------------

describe("hard exclusion #1 — SRRV Smile", () => {
  const SMILE_BARE_FACT_RE = /smile\s+(was|is|has been)\s+discontinued/i;
  const SMILE_SAFE_PHRASE_RE =
    /no longer appears? on( the)? (pra'?s )?authoritative/i;

  it("guilt: the bare-fact pattern fires on a known-bad claim", () => {
    expect(
      SMILE_BARE_FACT_RE.test("SRRV Smile was discontinued in 2025."),
    ).toBe(true);
  });

  it("innocence: the mandate's own safe phrasing does not trip the bare-fact pattern, and does carry the safe phrase", () => {
    const safe =
      "Smile no longer appears on PRA's authoritative tier page as of 2026-08-24.";
    expect(SMILE_BARE_FACT_RE.test(safe)).toBe(false);
    expect(SMILE_SAFE_PHRASE_RE.test(safe)).toBe(true);
  });

  it("fails if any dataset entry mentions Smile as a bare discontinuation fact, or without the inference-safe phrase", () => {
    const mentions = allStrings.filter((e) => /\bsmile\b/i.test(e.value));
    for (const m of mentions) {
      expect(
        SMILE_BARE_FACT_RE.test(m.value),
        `bare-fact Smile discontinuation claim at ${m.path}: "${m.value}"`,
      ).toBe(false);
      expect(
        SMILE_SAFE_PHRASE_RE.test(m.value),
        `Smile mentioned without the inference-safe phrase at ${m.path}: "${m.value}"`,
      ).toBe(true);
    }
  });

  it("today's dataset takes the safer option the mandate allowed: Smile is omitted entirely", () => {
    expect(allStrings.some((e) => /\bsmile\b/i.test(e.value))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Exclusion #2 — SRRV Courtesy deposit figures never quoted at all.
// ---------------------------------------------------------------------------

describe("hard exclusion #2 — SRRV Courtesy", () => {
  const COURTESY_RE = /\bcourtesy\b/i;

  it("guilt: the courtesy pattern fires on a known-bad row label", () => {
    expect(
      COURTESY_RE.test(
        "SRRV Courtesy (Foreign Nationals): USD 1,500 (age 50+)",
      ),
    ).toBe(true);
  });

  it("fails if any dataset entry mentions SRRV Courtesy at all (garbled source markup)", () => {
    const hits = allStrings.filter((e) => COURTESY_RE.test(e.value));
    expect(hits, hits.map((h) => `${h.path}: ${h.value}`).join("\n")).toEqual(
      [],
    );
  });
});

// ---------------------------------------------------------------------------
// Exclusion #3 — Malaysia naturalisation/citizenship claim out of scope.
// ---------------------------------------------------------------------------

describe("hard exclusion #3 — Malaysia naturalisation/citizenship", () => {
  const NATURALISATION_RE = /naturali[sz]ation|citizenship/i;

  function malaysiaStrings(): StringEntry[] {
    return [
      ...stringsUnder(programmesFor("Malaysia"), "malaysiaProgramme"),
      ...stringsUnder(MALAYSIA_MM2H_TIERS, "MALAYSIA_MM2H_TIERS"),
    ];
  }

  it("guilt: the pattern fires on the known-bad, out-of-scope claim", () => {
    expect(
      NATURALISATION_RE.test(
        "MM2H offers no naturalisation pathway despite 2024 policy ambiguity.",
      ),
    ).toBe(true);
    expect(
      NATURALISATION_RE.test(
        "A path to Malaysian citizenship remains unclear.",
      ),
    ).toBe(true);
  });

  it("fails if the Malaysia rows mention naturalisation or citizenship", () => {
    const hits = malaysiaStrings().filter((e) =>
      NATURALISATION_RE.test(e.value),
    );
    expect(hits, hits.map((h) => `${h.path}: ${h.value}`).join("\n")).toEqual(
      [],
    );
  });
});

// ---------------------------------------------------------------------------
// Exclusion #4 — the wrong Thailand tax-rate claim never appears near the
// pensioner/wealthy-citizen rows. The data itself is written to describe
// the correct exemption WITHOUT the literal digits, precisely so this test
// can be a clean, strict, unambiguous absence check rather than a claim-
// pattern heuristic that a future edit could quietly satisfy while still
// misattributing the rate.
// ---------------------------------------------------------------------------

describe("hard exclusion #4 — Thailand's wrong tax-rate figure", () => {
  const SEVENTEEN_PERCENT_RE = /17\s*%/;

  function thailandStrings(): StringEntry[] {
    return stringsUnder(programmesFor("Thailand"), "thailandProgramme");
  }

  it("guilt: the pattern fires on the known-wrong claim", () => {
    expect(
      SEVENTEEN_PERCENT_RE.test(
        "Thailand LTR grants a 17% personal income tax cap for Wealthy Pensioner holders.",
      ),
    ).toBe(true);
  });

  it("fails if '17%' appears anywhere in the Thailand rows", () => {
    const hits = thailandStrings().filter((e) =>
      SEVENTEEN_PERCENT_RE.test(e.value),
    );
    expect(hits, hits.map((h) => `${h.path}: ${h.value}`).join("\n")).toEqual(
      [],
    );
  });

  it("the correct exemption claim is present and does not need the wrong figure to state it", () => {
    const thailand = COUNTRY_PROGRAMMES.find(
      (p) => p.id === "thailand_ltr_wealthy_pensioner",
    );
    expect(thailand?.taxTreatment?.value.toLowerCase()).toContain("exemption");
    expect(thailand?.taxTreatment?.value.toLowerCase()).toContain(
      "foreign-sourced income",
    );
  });
});

// ---------------------------------------------------------------------------
// Exclusion #5 — Portugal D7's income floor is a formula, never a frozen
// number, and the RMMG value is a separately dated field.
// ---------------------------------------------------------------------------

describe("hard exclusion #5 — Portugal D7 income floor is a formula, not a frozen number", () => {
  it("the formula export carries percentages, a legal basis, and a SEPARATELY DATED RMMG value", () => {
    expect(PORTUGAL_D7_INCOME_FORMULA.principalPercentOfRmmg.value).toBe(100);
    expect(PORTUGAL_D7_INCOME_FORMULA.additionalAdultPercentOfRmmg.value).toBe(
      50,
    );
    expect(PORTUGAL_D7_INCOME_FORMULA.dependentChildPercentOfRmmg.value).toBe(
      30,
    );
    expect(PORTUGAL_D7_INCOME_FORMULA.legalBasis.value).toMatch(/1563\/2007/);
    // The RMMG value must carry its OWN date, distinct from the formula's —
    // that is what makes it safe to update in isolation next year.
    expect(
      PORTUGAL_D7_INCOME_FORMULA.rmmg2026MonthlyEur.sourceLastUpdated,
    ).not.toBe(PORTUGAL_D7_INCOME_FORMULA.legalBasis.sourceLastUpdated);
  });

  it("the arithmetic holds: 100% of the 2026 RMMG resolves to EUR 920 for a single applicant", () => {
    const rmmg = PORTUGAL_D7_INCOME_FORMULA.rmmg2026MonthlyEur.value;
    const principalPct =
      PORTUGAL_D7_INCOME_FORMULA.principalPercentOfRmmg.value;
    expect((rmmg * principalPct) / 100).toBe(920);
  });

  it("no programme row hardcodes the D7 income floor as a bare number without the word 'formula' or a percentage nearby", () => {
    const d7 = COUNTRY_PROGRAMMES.find((p) => p.id === "portugal_d7");
    const income = d7?.incomeRequirement?.value ?? "";
    expect(income.toLowerCase()).toContain("formula");
    expect(income).toMatch(/100%/);
  });
});

// ---------------------------------------------------------------------------
// Exclusion #6 — own-name custody is "confirmed" for Indonesia only.
// ---------------------------------------------------------------------------

describe("hard exclusion #6 — own-name custody confirmed for Indonesia only", () => {
  function findConfirmedNonIndonesiaViolations(
    programmes: readonly CountryProgramme[],
  ): string[] {
    return programmes
      .filter(
        (p) =>
          p.country !== "Indonesia" &&
          p.custody.assetOwnNameStatus.value === "confirmed",
      )
      .map((p) => p.id);
  }

  it("guilt: the check fires on a deliberately mutated fixture", () => {
    const mutated = COUNTRY_PROGRAMMES.map((p) =>
      p.id === "thailand_ltr_wealthy_pensioner"
        ? {
            ...p,
            custody: {
              ...p.custody,
              assetOwnNameStatus: {
                ...p.custody.assetOwnNameStatus,
                value: "confirmed" as const,
              },
            },
          }
        : p,
    );
    expect(findConfirmedNonIndonesiaViolations(mutated)).toEqual([
      "thailand_ltr_wealthy_pensioner",
    ]);
  });

  it("fails if any non-Indonesia programme asserts own-name custody as confirmed", () => {
    expect(findConfirmedNonIndonesiaViolations(COUNTRY_PROGRAMMES)).toEqual([]);
  });

  it("Indonesia's own-name custody IS confirmed (positive pin — SSOT)", () => {
    const indonesia = programmesFor("Indonesia");
    expect(indonesia.length).toBeGreaterThan(0);
    for (const p of indonesia) {
      expect(p.custody.assetOwnNameStatus.value).toBe("confirmed");
    }
  });
});

// ---------------------------------------------------------------------------
// Every cell carries a source URL, a captured date, and a confidence tag —
// structurally, not as prose. "for a residency programme, an undated figure
// is unusable."
// ---------------------------------------------------------------------------

describe("every SourcedCell carries a source URL, a valid date, and a confidence tag", () => {
  const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const VALID_CONFIDENCE = new Set([
    "primary_confirmed",
    "secondary_consensus",
    "unverified",
  ]);

  function findMissingProvenance(cells: FoundCell[]): string[] {
    const violations: string[] = [];
    for (const { path, cell } of cells) {
      if (!cell.sourceUrl || typeof cell.sourceUrl !== "string") {
        violations.push(`${path}: missing/empty sourceUrl`);
      }
      if (!ISO_DATE_RE.test(String(cell.capturedDate))) {
        violations.push(`${path}: invalid capturedDate "${cell.capturedDate}"`);
      }
      if (!VALID_CONFIDENCE.has(String(cell.confidence))) {
        violations.push(`${path}: invalid confidence "${cell.confidence}"`);
      }
      if (
        cell.sourceLastUpdated !== null &&
        !ISO_DATE_RE.test(String(cell.sourceLastUpdated))
      ) {
        violations.push(
          `${path}: invalid sourceLastUpdated "${cell.sourceLastUpdated}"`,
        );
      }
    }
    return violations;
  }

  it("guilt: the provenance check fires on deliberately broken fixture cells", () => {
    const broken: FoundCell[] = [
      {
        path: "fixture.missingSourceUrl",
        cell: {
          value: "x",
          sourceUrl: "",
          capturedDate: "2026-08-24",
          sourceLastUpdated: null,
          confidence: "primary_confirmed",
        },
      },
      {
        path: "fixture.badDate",
        cell: {
          value: "x",
          sourceUrl: "https://example.com",
          capturedDate: "not-a-date",
          sourceLastUpdated: null,
          confidence: "primary_confirmed",
        },
      },
      {
        path: "fixture.badConfidence",
        cell: {
          value: "x",
          sourceUrl: "https://example.com",
          capturedDate: "2026-08-24",
          sourceLastUpdated: null,
          confidence: "vibes" as unknown as SourcedCell<string>["confidence"],
        },
      },
    ];
    expect(findMissingProvenance(broken).length).toBe(3);
  });

  it("fails if any real dataset cell lacks a source URL, valid captured date, or valid confidence tag", () => {
    expect(findMissingProvenance(allCells)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// No Bali Zero price, no client PII — this is a comparison of foreign
// government programmes, not a Bali Zero offer.
// ---------------------------------------------------------------------------

describe("no Bali Zero price, no client PII", () => {
  it("no string mentions Bali Zero or an IDR price figure", () => {
    const hits = allStrings.filter(
      (e) => /bali\s*zero/i.test(e.value) || /\bIDR\s*[0-9]/i.test(e.value),
    );
    expect(hits, hits.map((h) => `${h.path}: ${h.value}`).join("\n")).toEqual(
      [],
    );
  });

  it("no string contains an email address or a phone-number-like literal", () => {
    const EMAIL_RE = /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i;
    const PHONE_RE = /\+?\d[\d\s-]{8,}\d/;
    const hits = allStrings.filter(
      (e) => EMAIL_RE.test(e.value) || PHONE_RE.test(e.value),
    );
    expect(hits, hits.map((h) => `${h.path}: ${h.value}`).join("\n")).toEqual(
      [],
    );
  });
});

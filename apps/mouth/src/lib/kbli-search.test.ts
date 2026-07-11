import { describe, expect, it } from "vitest";
import { getSuggestions, searchCodes } from "./kbli-search";
import type { KBLICode, KBLIRiskCategory } from "./kbli-types";

function makeCode(
  overrides: Partial<KBLICode> & Pick<KBLICode, "code" | "titleEn" | "titleId">,
): KBLICode {
  const riskCategory: KBLIRiskCategory = "Rendah";

  return {
    description: "Baseline description for a business activity.",
    section: "G",
    sectionName: "Trade",
    pma: {
      status: "open",
      maxForeign: 100,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
      capSpecial: false,
      capVerified: true,
      routeTo: null,
    },
    licensing: [
      {
        scales: ["Mikro", "Kecil"],
        riskCategory,
        licenseType: "NIB",
        requirements: [],
        timeframe: "Immediately",
        obligations: [],
        authority: "OSS",
        fictivePositive: true,
      },
    ],
    transition: {
      mappingStatus: "MATCH_LANGSUNG",
      previousCodes: [],
    },
    tier: "bronze",
    keywords: [],
    ...overrides,
  };
}

const restaurant = makeCode({
  code: "56101",
  titleEn: "Restaurant and mobile food service activities",
  titleId: "Restoran dan penyediaan makanan keliling",
  description:
    "Restaurants, warungs, and food service venues serving customers on site.",
  tier: "gold",
  keywords: ["restaurant", "warung", "food service"],
});

const software = makeCode({
  code: "62010",
  titleEn: "Software development activities",
  titleId: "Aktivitas pengembangan perangkat lunak",
  description: "Software products and application development services.",
  keywords: ["software", "application", "SaaS"],
});

const closedHotel = makeCode({
  code: "55110",
  titleEn: "Hotel accommodation",
  titleId: "Hotel berbintang",
  description: "Hotel accommodation services with higher risk licensing.",
  pma: {
    status: "closed",
    maxForeign: 0,
    condition: "Domestic investment only",
    isPriority: false,
    note: null,
    source: null,
    capSpecial: false,
    capVerified: true,
    routeTo: null,
  },
  licensing: [
    {
      scales: ["Besar"],
      riskCategory: "Tinggi",
      licenseType: "Business License",
      requirements: ["Environmental approval"],
      timeframe: "Variable",
      obligations: [],
      authority: "OSS",
      fictivePositive: false,
    },
  ],
  keywords: ["hotel", "accommodation"],
});

const codes = [restaurant, software, closedHotel];

describe("searchCodes", () => {
  it("returns a perfect exact-code match before broader relevance scoring", () => {
    const results = searchCodes(codes, "56 101");

    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      code: restaurant,
      score: 100,
      matchType: "exact_code",
    });
  });

  it("keeps prefix code matches above weaker keyword matches", () => {
    const results = searchCodes(codes, "620");

    expect(results[0]).toMatchObject({
      code: software,
      matchType: "exact_code",
    });
    expect(results[0].score).toBeGreaterThan(90);
  });

  it("applies PMA and risk filters before scoring", () => {
    const openLowRisk = searchCodes(codes, "hotel", {
      pmaStatus: "open",
      riskCategory: "Rendah",
    });
    const closedHighRisk = searchCodes(codes, "hotel", {
      pmaStatus: "closed",
      riskCategory: "Tinggi",
    });

    expect(openLowRisk).toEqual([]);
    expect(closedHighRisk).toHaveLength(1);
    expect(closedHighRisk[0].code.code).toBe("55110");
  });

  it("falls back to fuzzy matching for typo-only queries", () => {
    const results = searchCodes(codes, "restarant");

    expect(results[0]).toMatchObject({
      code: restaurant,
      matchType: "semantic",
    });
    expect(results[0].score).toBeGreaterThan(0);
  });

  it("returns an empty result for blank queries", () => {
    expect(searchCodes(codes, "   ")).toEqual([]);
  });
});

describe("getSuggestions", () => {
  it("orders suggestions by closest edit distance and then content tier", () => {
    const silverRestaurant = makeCode({
      code: "56102",
      titleEn: "Restarant consultancy",
      titleId: "Konsultan restoran",
      tier: "silver",
      keywords: ["restarant"],
    });

    const suggestions = getSuggestions(
      [restaurant, silverRestaurant, software],
      "restarant",
      3,
    );

    expect(suggestions.map((item) => item.code.code)).toEqual([
      "56102",
      "56101",
    ]);
    expect(suggestions[0]).toMatchObject({
      distance: 0,
      matchedOn: "Restarant consultancy",
    });
  });

  it("respects the requested suggestion limit", () => {
    const suggestions = getSuggestions(codes, "hotel", 1);

    expect(suggestions).toHaveLength(1);
    expect(suggestions[0].code.code).toBe("55110");
  });
});

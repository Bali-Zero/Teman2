import { describe, expect, it } from "vitest";
import { getSuggestions, searchCodes } from "./kbli-search";
import type { KBLICode, KBLIRiskCategory } from "./kbli-types";

function makeCode(overrides: Partial<KBLICode> & { code: string }): KBLICode {
  const riskCategory: KBLIRiskCategory = "Rendah";
  const { code, ...rest } = overrides;

  return {
    code,
    titleId: "Aktivitas konsultasi manajemen",
    titleEn: "Management consulting activities",
    description: "General business advisory services for companies in Bali.",
    section: "M",
    sectionName: "Professional activities",
    pma: {
      status: "open",
      maxForeign: 100,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
    },
    licensing: [
      {
        scales: ["Mikro", "Kecil"],
        riskCategory,
        licenseType: "NIB",
        requirements: [],
        timeframe: "Instant",
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
    ...rest,
  };
}

const restaurant = makeCode({
  code: "56101",
  titleId: "Restoran dan rumah makan",
  titleEn: "Restaurants and mobile food service activities",
  description: "Food service for restaurants, cafes, and dining venues.",
  tier: "gold",
  keywords: ["restaurant", "cafe", "food service"],
});

const catering = makeCode({
  code: "56210",
  titleId: "Jasa boga untuk acara",
  titleEn: "Event catering activities",
  description: "Catering services for private events and business functions.",
  pma: {
    status: "restricted",
    maxForeign: 67,
    condition: "Local partner required",
    isPriority: false,
    note: null,
    source: null,
  },
  licensing: [
    {
      scales: ["Menengah", "Besar"],
      riskCategory: "Menengah Tinggi",
      licenseType: "NIB + Standard Certificate",
      requirements: ["Hygiene certificate"],
      timeframe: "10 days",
      obligations: [],
      authority: "OSS",
      fictivePositive: false,
    },
  ],
  tier: "silver",
  keywords: ["catering", "events"],
});

const software = makeCode({
  code: "62019",
  titleId: "Aktivitas pemrograman komputer lainnya",
  titleEn: "Other software publishing and programming activities",
  description: "Software development, SaaS operations, and platform engineering.",
  keywords: ["software", "saas", "programming"],
});

describe("searchCodes", () => {
  it("returns a cleaned exact code match before keyword scoring", () => {
    const results = searchCodes([software, restaurant], "56 101");

    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      code: expect.objectContaining({ code: "56101" }),
      score: 100,
      matchType: "exact_code",
    });
  });

  it("keeps numeric prefix matches ahead of lower relevance results without duplicates", () => {
    const results = searchCodes([restaurant, catering, software], "56");

    expect(results.slice(0, 2).map((result) => result.code.code)).toEqual([
      "56101",
      "56210",
    ]);
    expect(new Set(results.map((result) => result.code.code)).size).toBe(
      results.length,
    );
    expect(results[0].matchType).toBe("exact_code");
    expect(results[1].matchType).toBe("exact_code");
  });

  it("applies PMA and risk filters before ranking search results", () => {
    const results = searchCodes([restaurant, catering, software], "events", {
      pmaStatus: "restricted",
      riskCategory: "Menengah Tinggi",
    });

    expect(results.map((result) => result.code.code)).toEqual(["56210"]);
  });

  it("matches Indonesian title and keyword words case-insensitively", () => {
    const results = searchCodes([restaurant, software], "  RUMAH makan ");

    expect(results[0].code.code).toBe("56101");
    expect(results[0].matchType).toBe("keyword");
  });

  it("falls back to fuzzy matching for close typos only when relevance misses", () => {
    const typoCandidate = makeCode({
      code: "56109",
      titleId: "Restoran kecil",
      titleEn: "Restaurant kiosk activities",
      pma: {
        status: "closed",
        maxForeign: 0,
        condition: null,
        isPriority: false,
        note: null,
        source: null,
      },
      tier: "bronze",
      keywords: [],
    });

    const results = searchCodes([typoCandidate], "restarant");

    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      code: expect.objectContaining({ code: "56109" }),
      matchType: "semantic",
    });
  });

  it("returns an empty result for blank queries", () => {
    expect(searchCodes([restaurant], "   ")).toEqual([]);
  });
});

describe("getSuggestions", () => {
  it("suggests close title and keyword matches sorted by distance then tier", () => {
    const bronzeRestaurant = makeCode({
      code: "56102",
      titleEn: "Restaurant support activities",
      titleId: "Aktivitas pendukung restoran",
      tier: "bronze",
      keywords: ["restaurant"],
    });
    const goldRestaurant = makeCode({
      code: "56103",
      titleEn: "Restaurant consulting",
      titleId: "Konsultasi restoran",
      tier: "gold",
      keywords: ["restaurant"],
    });

    const suggestions = getSuggestions(
      [bronzeRestaurant, goldRestaurant],
      "restarant",
    );

    expect(suggestions.map((suggestion) => suggestion.code.code)).toEqual([
      "56103",
      "56102",
    ]);
    expect(suggestions[0].matchedOn).toContain("Restaurant");
  });

  it("honors the requested suggestion limit and ignores distant words", () => {
    const suggestions = getSuggestions(
      [restaurant, catering, software],
      "restarant",
      1,
    );

    expect(suggestions).toHaveLength(1);
    expect(suggestions[0].code.code).toBe("56101");
    expect(suggestions.some((suggestion) => suggestion.code.code === "62019"))
      .toBe(false);
  });

  it("returns no suggestions for blank queries", () => {
    expect(getSuggestions([restaurant], "")).toEqual([]);
  });
});

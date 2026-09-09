import { describe, expect, it } from "vitest";
import { parseCoordinates } from "./coordinates";
import {
  parseAnalyzeInput,
  projectAnalysis,
  projectZones,
} from "./property-contract";
import { filterDeadlines, TAX_ARCHIVE, taxCalendarIcal } from "./tax-calendar";

describe("coordinate contract", () => {
  it.each([
    "-8.5, 115.25",
    "−8.5 115.25",
    "8°30'0\"S, 115°15'0\"E",
    "115°15'0\"E 8°30'0\"S",
    "https://www.google.com/maps?q=-8.5,115.25",
    "https://maps.google.com/maps/@-8.5,115.25,17z",
  ])("preserves supported format %s", (input) => {
    expect(parseCoordinates(input)).toEqual({ lat: -8.5, lng: 115.25 });
  });
  it.each([
    "91,115",
    "-8,181",
    "-8,115 trailing words",
    "NaN,115",
    "https://example.test/?q=-8,115",
    "https://maps.app.goo.gl/short",
    "8°60'0\"S 115°0'0\"E",
  ])("rejects ambiguous or out-of-range input %s", (input) => {
    expect(parseCoordinates(input)).toBeNull();
  });
});

describe("public data projection", () => {
  it("forwards only supported calculation inputs, including domestic false", () => {
    expect(
      parseAnalyzeInput({
        lat: -8,
        lng: 115,
        kbli_code: "12345",
        is_pma: false,
        land_size_m2: 100,
        price_idr: 1000,
        investor_profile: { name: "SYNTHETIC_PRIVATE" },
        geo_data: { score: 100 },
      }),
    ).toEqual({
      lat: -8,
      lng: 115,
      kbli_code: "12345",
      is_pma: false,
      land_size_m2: 100,
      price_idr: 1000,
    });
    for (const input of [
      { lat: -100, lng: 115 },
      { lat: -8, lng: 115, price_idr: -10 },
      { lat: -8, lng: 115, is_pma: "false" },
      { lat: -8, lng: 115, kbli_code: "123" },
    ])
      expect(parseAnalyzeInput(input)).toBeNull();
  });
  it("retains actual calculations through repeated projection and strips identities", () => {
    const result = projectAnalysis({
      status: "analyzed",
      investor_name: "SYNTHETIC_PRIVATE",
      zone: {
        code: "TEST",
        name: "Fixture zone",
        overlays: { heritage: "Recorded" },
        owner: "SYNTHETIC_PRIVATE",
      },
      verdict: {
        label: "YELLOW",
        score: 42,
        can_invest: false,
        risk_level: "MEDIUM",
        breakdown: {
          risk: { score: 4, max: 10 },
          roi: { score: null, max: 30 },
        },
        hard_blocks: ["Fixture restriction"],
        modifiers: ["Fixture note"],
      },
      opportunities: [
        {
          title_en: "Fixture activity",
          category_en: "Fixture category",
          pma_open: false,
        },
        {
          title_en: "Fixture activity",
          category_en: "Fixture category",
          pma_open: false,
        },
      ],
      roi: {
        golden_strategy: { roi: 12.25, bey: 8 },
        total_investment_idr: 1000,
      },
      property_tax: { annual_pbb: 10 },
      intel_articles: ["SYNTHETIC_PRIVATE"],
    });
    expect(result.verdict?.score).toBe(42);
    expect(result.verdict?.breakdown.risk).toEqual({ score: 4, max: 10 });
    expect(result.opportunities).toHaveLength(1);
    expect(result.opportunities[0].pma_open).toBe(false);
    expect(result.roi?.roi).toBe(12.25);
    expect(result.overlays.heritage).toBe("Recorded");
    expect(projectAnalysis(result)).toEqual(result);
    expect(JSON.stringify(result)).not.toContain("SYNTHETIC_PRIVATE");
  });
  it("keeps missing coverage and calculator failure explicit", () => {
    expect(projectAnalysis({ status: "analyzed", zone: null }).zone).toBeNull();
    const failed = projectAnalysis({
      roi: { error: "PRIVATE_INTERNAL_ERROR" },
    });
    expect(failed.roi).toEqual({ available: false });
    expect(projectAnalysis(failed).roi).toEqual({ available: false });
    expect(JSON.stringify(failed)).not.toContain("PRIVATE_INTERNAL_ERROR");
  });
  it("keeps real polygon coordinates while excluding extra dimensions and unsafe colors", () => {
    const result = projectZones({
      features: [
        {
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [115, -8, "PRIVATE"],
                [116, -8],
                [116, -9],
                [115, -8],
              ],
            ],
          },
          properties: {
            zone_code: "TEST",
            color: "url(https://external.test)",
            client: "PRIVATE",
          },
        },
        {
          geometry: { type: "Polygon", coordinates: [[[300, -8]]] },
          properties: {},
        },
      ],
    });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].geometry.coordinates[0][0]).toEqual([115, -8]);
    expect(result.features[0].properties).toEqual({ zone_code: "TEST" });
    expect(JSON.stringify(result)).not.toContain("PRIVATE");
  });
});

describe("historical calendar", () => {
  it("keeps national records when filtering a regency and then intersects kind", () => {
    const regency = filterDeadlines(TAX_ARCHIVE, "ALL", "Badung");
    expect(regency).toHaveLength(5);
    expect(regency.some((d) => d.regency === "Gianyar")).toBe(false);
    expect(
      filterDeadlines(TAX_ARCHIVE, "PB1", "Badung").map((d) => d.id),
    ).toEqual(["pb1-badung"]);
  });
  it("exports the selected historical dates without rolling them forward or creating reminders", () => {
    const ics = taxCalendarIcal(filterDeadlines(TAX_ARCHIVE, "PB1", "Badung"));
    expect(ics).toContain(
      "DTSTART;VALUE=DATE:20260510\r\nDTEND;VALUE=DATE:20260511",
    );
    expect(ics).toContain("[UNVERIFIED ARCHIVE]");
    expect(ics).not.toMatch(/RRULE|VALARM|Gianyar/);
    expect(ics.match(/BEGIN:VEVENT/g)).toHaveLength(1);
    for (const line of ics.split("\r\n"))
      expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
    const escaped = taxCalendarIcal([
      { ...TAX_ARCHIVE[0], title: "a,b;c\\d\ne" },
    ]);
    expect(escaped).toContain("a\\,b\\;c\\\\d\\ne");
  });
});

import { SERVICES, pricingBackedVisaService } from "./book-data";
import { getPricingSnapshotEntry } from "@/lib/pricing-snapshot";

const E33F_CATEGORY = "kitas_permits";
const E33F_KEY = "E33F Second Home Senior (1 Year, Offshore)";
const E33F_SERVICE_KEY = `${E33F_CATEGORY}:${E33F_KEY}`;
const SPONSOR_SENTENCE =
  "A sponsor (penjamin) is required; Bali Zero can act as one.";

describe("book E33F sponsor highlight and pricingBackedVisaService", () => {
  it("throws when highlight is not verbatim in the catalogue row description_en (guilt)", () => {
    expect(() =>
      pricingBackedVisaService(
        "kitas_permits",
        "E33F Second Home Senior (1 Year, Offshore)",
        undefined,
        "this sentence is not in the row",
      ),
    ).toThrow(/does not contain highlight/);
  });

  it("throws when highlight is blank or whitespace-only (guilt)", () => {
    expect(() =>
      pricingBackedVisaService(
        "kitas_permits",
        "E33F Second Home Senior (1 Year, Offshore)",
        undefined,
        "",
      ),
    ).toThrow(/does not contain highlight/);
    expect(() =>
      pricingBackedVisaService(
        "kitas_permits",
        "E33F Second Home Senior (1 Year, Offshore)",
        undefined,
        "   ",
      ),
    ).toThrow(/does not contain highlight/);
  });

  it("places the exact sponsor sentence at features[0] on E33F while keeping tagline unchanged (guilt)", () => {
    const e33f = SERVICES.find((s) => s.serviceKey === E33F_SERVICE_KEY);
    const entry = getPricingSnapshotEntry(E33F_CATEGORY, E33F_KEY);
    expect(e33f).toBeDefined();
    expect(entry).toBeDefined();
    expect(e33f!.features[0]).toBe(SPONSOR_SENTENCE);
    expect(e33f!.tagline).toBe(entry!.description_en);
    expect(e33f!.tagline).toContain(SPONSOR_SENTENCE);
  });

  it("keeps the remaining E33F features equal to the filtered snapshot fields in order (guilt)", () => {
    const e33f = SERVICES.find((s) => s.serviceKey === E33F_SERVICE_KEY);
    const entry = getPricingSnapshotEntry(E33F_CATEGORY, E33F_KEY);
    expect(e33f).toBeDefined();
    expect(entry).toBeDefined();
    const expectedRemaining = [
      entry!.duration,
      entry!.validity,
      entry!.notes,
    ].filter((v): v is string => Boolean(v?.trim()));
    expect(e33f!.features.slice(1)).toEqual(expectedRemaining);
  });

  it("leaves every other pricing-backed visa service in SERVICES with unhighlighted snapshot features (innocence)", () => {
    const otherVisaServices = SERVICES.filter(
      (s) =>
        s.category === "visa" &&
        Boolean(s.pricingCategory) &&
        Boolean(s.pricingItemKey) &&
        s.serviceKey !== E33F_SERVICE_KEY,
    );
    expect(otherVisaServices.length).toBeGreaterThan(0);
    let nonEmptyCount = 0;
    for (const service of otherVisaServices) {
      const entry = getPricingSnapshotEntry(
        service.pricingCategory!,
        service.pricingItemKey!,
      );
      expect(entry).toBeDefined();
      const expected = [entry!.duration, entry!.validity, entry!.notes].filter(
        (v): v is string => Boolean(v?.trim()),
      );
      if (expected.length > 0) {
        nonEmptyCount += 1;
      }
      expect(service.features).toEqual(expected);
    }
    expect(nonEmptyCount).toBeGreaterThan(0);
  });

  it("yields no highlight and preserves positional badge when called without highlight (innocence)", () => {
    const built = pricingBackedVisaService(
      "single_entry_visas",
      "C1 Tourism",
      "Most popular",
    );
    const entry = getPricingSnapshotEntry("single_entry_visas", "C1 Tourism");
    expect(entry).toBeDefined();
    const expected = [entry!.duration, entry!.validity, entry!.notes].filter(
      (v): v is string => Boolean(v?.trim()),
    );
    expect(built.features).toEqual(expected);
    expect(built.badge).toBe("Most popular");
  });
});

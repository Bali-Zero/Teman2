import { describe, expect, it } from "vitest";
import { dict, translate } from "./i18n";

describe("i18n.ts — EN/ID key parity", () => {
  it("has an identical key set in both languages (runtime defense-in-depth for the compile-time `satisfies` check)", () => {
    const enKeys = Object.keys(dict.en).sort();
    const idKeys = Object.keys(dict.id).sort();
    expect(idKeys).toEqual(enKeys);
  });

  // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M6): the old lead promised an
  // always-human review that stopped being true after A1'/A3-B — see
  // `q.review_gate.hint`'s new value. A literal, not a family: a fixture
  // pinned against a shrinking list would silently stop testing anything
  // the day the list it derives from shrinks.
  it("never ships the retired 'a human reviews your case' promise (M6)", () => {
    const retired = "Any of these means a human reviews your case";
    for (const [lang, table] of Object.entries(dict)) {
      for (const [key, value] of Object.entries(table)) {
        expect(
          value,
          `${lang}.${key} still carries the retired promise`,
        ).not.toContain(retired);
      }
    }
  });

  it("has no empty-string values in either language", () => {
    for (const [lang, table] of Object.entries(dict)) {
      for (const [key, value] of Object.entries(table)) {
        expect(value.length, `${lang}.${key} is empty`).toBeGreaterThan(0);
      }
    }
  });

  it("ID copy uses formal 'Anda', never 'kamu' (design doc §3 register rule)", () => {
    for (const [key, value] of Object.entries(dict.id)) {
      expect(value.toLowerCase(), `id.${key} uses "kamu"`).not.toMatch(
        /\bkamu\b/,
      );
    }
  });

  it("every English string that says 'qualifying' has an Indonesian twin that says 'memenuhi syarat'", () => {
    // Eligibility sense only: "qualification" (credentials) is deliberately excluded.
    const qualifyingKeys = (
      Object.keys(dict.en) as Array<keyof typeof dict.en>
    ).filter((key) => /\bqualif(y|ying|ies|ied)\b/i.test(dict.en[key]));
    expect(qualifyingKeys.length).toBeGreaterThan(0);
    expect(qualifyingKeys).toContain("q.investment_vehicle.opt.property");
    expect(qualifyingKeys).toContain("q.secondhome_basis.opt.property");
    for (const key of qualifyingKeys) {
      expect(dict.id[key], `id.${key} must say "memenuhi syarat"`).toMatch(
        /memenuhi syarat/i,
      );
    }
  });

  it("pins q.investment_vehicle.opt.property in both languages and keeps the ID label figure-free", () => {
    expect(dict.en["q.investment_vehicle.opt.property"]).toBe(
      "A qualifying property arrangement",
    );
    expect(dict.id["q.investment_vehicle.opt.property"]).toBe(
      "Properti yang memenuhi syarat",
    );
    expect(dict.id["q.investment_vehicle.opt.property"]).not.toMatch(/\d/);
  });
});

describe("i18n.ts — translate()", () => {
  it("interpolates {{vars}}", () => {
    expect(translate("en", "paths.counter.aria", { count: 3 })).toBe(
      "3 interview branches remaining",
    );
    expect(translate("id", "paths.counter.aria", { count: 3 })).toBe(
      "3 cabang wawancara tersisa",
    );
  });

  it("returns the raw string unchanged when there is nothing to interpolate", () => {
    expect(translate("en", "back.button")).toBe("Back");
    expect(translate("id", "back.button")).toBe("Kembali");
  });

  it("resolves {{plural:singular|plural}} to the singular form for count === 1, never '1 interview branches' (R3 D-V7)", () => {
    expect(translate("en", "paths.counter.label", { count: 1 })).toBe(
      "1 interview branch",
    );
    expect(translate("en", "paths.counter.aria", { count: 1 })).toBe(
      "1 interview branch remaining",
    );
    expect(translate("en", "confirmation.paths_remaining", { count: 1 })).toBe(
      "1 interview branch remaining",
    );
  });

  it("resolves {{plural:singular|plural}} to the plural form for any count !== 1", () => {
    expect(translate("en", "paths.counter.label", { count: 3 })).toBe(
      "3 interview branches",
    );
    expect(translate("en", "paths.counter.label", { count: 0 })).toBe(
      "0 interview branches",
    );
    expect(translate("en", "confirmation.paths_remaining", { count: 5 })).toBe(
      "5 interview branches remaining",
    );
  });

  it("Bahasa Indonesia does not inflect for number, so ID copy is identical at count 1 and count 3", () => {
    expect(translate("id", "paths.counter.label", { count: 1 })).toBe(
      "1 cabang wawancara",
    );
    expect(translate("id", "paths.counter.label", { count: 3 })).toBe(
      "3 cabang wawancara",
    );
  });
});

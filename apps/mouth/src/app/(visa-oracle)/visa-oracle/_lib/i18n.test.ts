import { describe, expect, it } from "vitest";
import { dict, translate } from "./i18n";

describe("i18n.ts — EN/ID key parity", () => {
  it("has an identical key set in both languages (runtime defense-in-depth for the compile-time `satisfies` check)", () => {
    const enKeys = Object.keys(dict.en).sort();
    const idKeys = Object.keys(dict.id).sort();
    expect(idKeys).toEqual(enKeys);
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

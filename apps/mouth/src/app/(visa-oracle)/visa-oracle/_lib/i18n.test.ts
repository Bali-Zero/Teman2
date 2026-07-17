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
      "3 paths remaining",
    );
    expect(translate("id", "paths.counter.aria", { count: 3 })).toBe(
      "3 jalur tersisa",
    );
  });

  it("returns the raw string unchanged when there is nothing to interpolate", () => {
    expect(translate("en", "back.button")).toBe("Back");
    expect(translate("id", "back.button")).toBe("Kembali");
  });
});

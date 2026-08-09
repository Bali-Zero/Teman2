import {
  ISO_ALPHA2_CODES,
  canonicalCountryCodes,
  getCountryOptions,
  isIsoAlpha2Code,
} from "./countries";

describe("ISO country registry", () => {
  it("contains the 249 current alpha-2 entries and rejects user-assigned ZZ", () => {
    expect(ISO_ALPHA2_CODES).toHaveLength(249);
    expect(isIsoAlpha2Code("ID")).toBe(true);
    expect(isIsoAlpha2Code("ZZ")).toBe(false);
  });

  it("canonicalizes language-neutral values without accepting arbitrary pairs", () => {
    expect(canonicalCountryCodes(["it", "ID", "IT"], true)).toBe("ID,IT");
    expect(canonicalCountryCodes(["ZZ"], true)).toBeNull();
    expect(canonicalCountryCodes(["ID", "IT"], false)).toBeNull();
  });

  it("localizes names while retaining the same country code", () => {
    const english = getCountryOptions("en").find(({ code }) => code === "ID");
    const indonesian = getCountryOptions("id").find(
      ({ code }) => code === "ID",
    );
    expect(english?.code).toBe("ID");
    expect(indonesian?.code).toBe("ID");
    expect(english?.name).toBeTruthy();
    expect(indonesian?.name).toBeTruthy();
  });
});

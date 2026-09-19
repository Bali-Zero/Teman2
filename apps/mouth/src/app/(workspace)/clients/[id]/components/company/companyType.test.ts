import { describe, it, expect } from "vitest";
import {
  COMPANY_TYPE_OPTIONS,
  normalizeCompanyType,
  companyTypeOptionsWithCurrent,
} from "./companyType";

describe("companyType — PT (local / PMDN)", () => {
  it("is a canonical option, not folded into PT PMA", () => {
    expect(COMPANY_TYPE_OPTIONS.some((o) => o.value === "PT")).toBe(true);
  });

  it("GUILT — companyTypeOptionsWithCurrent('PT') returns the canonical list, no '(unrecognized)' entry", () => {
    const options = companyTypeOptionsWithCurrent("PT");
    expect(options).toEqual(COMPANY_TYPE_OPTIONS);
    expect(options.some((o) => o.label.includes("unrecognized"))).toBe(false);
    expect(options.some((o) => o.value === "PT")).toBe(true);
  });

  it("normalizeCompanyType('PT') is idempotent", () => {
    expect(normalizeCompanyType("PT")).toBe("PT");
  });

  it.each(["PMDN", "PT_PMDN", "PT PMDN"])(
    "maps legacy alias %s to PT",
    (alias) => {
      expect(normalizeCompanyType(alias)).toBe("PT");
    },
  );

  it("INNOCENCE — PMA still maps to PT PMA, PT does not steal it", () => {
    expect(normalizeCompanyType("PMA")).toBe("PT PMA");
    const options = companyTypeOptionsWithCurrent("PMA");
    expect(options.find((o) => o.value === "PT PMA")).toBeTruthy();
  });

  it("INNOCENCE — a genuinely unknown value is still returned unchanged with an '(unrecognized)' option", () => {
    expect(normalizeCompanyType("Yayasan")).toBe("Yayasan");
    const options = companyTypeOptionsWithCurrent("Yayasan");
    expect(options[0]).toEqual({
      value: "Yayasan",
      label: "Yayasan (unrecognized)",
    });
  });
});

import { describe, expect, it } from "vitest";

import { SERVICES_DATA } from "./services_data";

// The official E28A page states the investor threshold as the applicant's own
// shareholding of at least IDR 10,000,000,000 in the sponsoring company.
describe("/services/visa investor eligibility requirement", () => {
  const eligibility = SERVICES_DATA.visa.requirements.eligibility;

  it("names the IDR 10 billion own shareholding in the sponsoring PT PMA", () => {
    const rows = eligibility.filter((r) => /Investor KITAS \(E28A\)/.test(r));
    expect(rows).toEqual([
      "For the Investor KITAS (E28A): your own shareholding of at least IDR 10 billion in the sponsoring PT PMA",
    ]);
  });

  it("no longer carries the vague 'minimum investment' bullet", () => {
    expect(eligibility.some((r) => /minimum investment/i.test(r))).toBe(false);
  });
});

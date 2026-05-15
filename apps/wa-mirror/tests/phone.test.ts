import { describe, expect, it } from "vitest";

import { normalizePhone, phoneSearchVariants } from "../bridge/phone.js";

describe("normalizePhone", () => {
  it("normalizes Indonesian local 08xxx numbers to canonical E.164", () => {
    expect(normalizePhone("0812 3456-7890")).toBe("+6281234567890");
  });

  it("normalizes 628xxx numbers to canonical E.164", () => {
    expect(normalizePhone("6281234567890")).toBe("+6281234567890");
  });

  it("keeps +628xxx numbers canonical after stripping separators", () => {
    expect(normalizePhone("+62 812-3456-7890")).toBe("+6281234567890");
  });

  it("normalizes over-zero-prefixed variants to the same canonical value", () => {
    expect(normalizePhone("0062 812 3456 7890")).toBe("+6281234567890");
  });
});

describe("phoneSearchVariants", () => {
  it("emits canonical, digit-only, and local variants for DB matching", () => {
    expect(phoneSearchVariants("0812 3456 7890")).toEqual([
      "+6281234567890",
      "6281234567890",
      "081234567890",
    ]);
  });
});

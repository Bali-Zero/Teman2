import { describe, expect, it } from "vitest";

import { isOwner } from "./owner";

describe("isOwner", () => {
  it("accepts configured owner email addresses", () => {
    expect(isOwner("zero@balizero.com")).toBe(true);
    expect(isOwner("antonellosiano@balizero.com")).toBe(true);
  });

  it("normalizes casing and whitespace before checking owner access", () => {
    expect(isOwner("  ZERO@BALIZERO.COM ")).toBe(true);
  });

  it("rejects missing or non-owner email addresses", () => {
    expect(isOwner(null)).toBe(false);
    expect(isOwner(undefined)).toBe(false);
    expect(isOwner("team@balizero.com")).toBe(false);
  });
});

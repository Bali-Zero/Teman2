import { describe, it, expect } from "vitest";
import { ENGLISH_TITLES } from "./kbli-english";

describe("ENGLISH_TITLES", () => {
  it("is a non-empty Record", () => {
    expect(Object.keys(ENGLISH_TITLES).length).toBeGreaterThan(0);
  });

  it("maps KBLI codes to English strings", () => {
    expect(typeof ENGLISH_TITLES["55101"]).toBe("string");
    expect(ENGLISH_TITLES["55101"]).toBe("Five-Star Hotel");
  });

  it("contains accommodation sector codes", () => {
    expect(ENGLISH_TITLES["55201"]).toBe("Homestay");
    expect(ENGLISH_TITLES["55203"]).toBe("Villa Rental");
  });

  it("contains food and beverage codes", () => {
    expect(ENGLISH_TITLES["56101"]).toBe("Restaurant");
  });

  it("has string keys that look like KBLI codes (digits only)", () => {
    for (const key of Object.keys(ENGLISH_TITLES)) {
      expect(key).toMatch(/^\d+$/);
    }
  });
});

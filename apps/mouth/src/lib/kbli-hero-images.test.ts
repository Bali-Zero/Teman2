import { describe, it, expect } from "vitest";
import { GOLD_HERO_IMAGES } from "./kbli-hero-images";

describe("GOLD_HERO_IMAGES", () => {
  it("is a non-empty Record", () => {
    expect(Object.keys(GOLD_HERO_IMAGES).length).toBeGreaterThan(0);
  });

  it("has string keys that look like KBLI codes (digits only)", () => {
    for (const key of Object.keys(GOLD_HERO_IMAGES)) {
      expect(key).toMatch(/^\d+$/);
    }
  });

  it("each entry has src, alt, and overlay fields", () => {
    for (const [code, entry] of Object.entries(GOLD_HERO_IMAGES)) {
      expect(entry.src).toBeTruthy();
      expect(typeof entry.src).toBe("string");
      expect(entry.alt).toBeTruthy();
      expect(typeof entry.alt).toBe("string");
      expect(entry.overlay).toBeTruthy();
      expect(typeof entry.overlay).toBe("string");
    }
  });

  it("src fields are Unsplash URLs", () => {
    const sample = Object.values(GOLD_HERO_IMAGES)[0];
    expect(sample.src).toContain("unsplash.com");
  });

  it("overlay fields contain linear-gradient", () => {
    const sample = Object.values(GOLD_HERO_IMAGES)[0];
    expect(sample.overlay).toContain("linear-gradient");
  });
});

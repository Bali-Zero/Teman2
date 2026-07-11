import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";
import { GOLD_HERO_IMAGES } from "./kbli-hero-images";

describe("GOLD_HERO_IMAGES (superseded by kbli-cover-design.ts)", () => {
  it("is an empty Record — no hardcoded per-code entries remain", () => {
    expect(GOLD_HERO_IMAGES).toEqual({});
  });

  it("source file contains no unsplash.com references", () => {
    const source = readFileSync(
      join(__dirname, "kbli-hero-images.ts"),
      "utf-8",
    );
    expect(source).not.toContain("unsplash.com");
  });
});

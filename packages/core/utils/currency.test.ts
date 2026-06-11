import { describe, it, expect } from "vitest";
import {
  formatIDR,
  formatIDRCompact,
  formatUSD,
  formatCurrency,
} from "./currency";

// id-ID currency output uses a non-breaking space between "Rp" and digits.
const nbsp = (s: string) => s.replace(/ /g, " ");

describe("formatIDR (full)", () => {
  it("formats with id-ID grouping and no decimals", () => {
    expect(nbsp(formatIDR(1_850_000))).toBe("Rp 1.850.000");
    expect(nbsp(formatIDR(0))).toBe("Rp 0");
    expect(nbsp(formatIDR(1_481))).toBe("Rp 1.481");
  });
});

describe("formatIDRCompact", () => {
  it("uses K/M/B suffixes — the single compact notation", () => {
    expect(formatIDRCompact(1_150_000_000)).toBe("Rp 1.15B");
    expect(formatIDRCompact(45_200_000)).toBe("Rp 45.2M");
    expect(formatIDRCompact(800_000)).toBe("Rp 800K");
    expect(formatIDRCompact(2_000_000)).toBe("Rp 2M");
    expect(formatIDRCompact(0)).toBe("Rp 0");
  });

  it("never emits the jt/rb id-ID compact units (P0.3)", () => {
    for (const n of [800_000, 45_200_000, 1_150_000_000]) {
      const out = formatIDRCompact(n);
      expect(out).not.toMatch(/\b(jt|rb|M\s|mily)/u);
    }
  });
});

describe("formatUSD / formatCurrency", () => {
  it("formats USD", () => {
    expect(formatUSD(1500)).toBe("$1,500");
  });

  it("routes by currency code, defaulting to IDR", () => {
    expect(formatCurrency(1500, "USD")).toBe("$1,500");
    expect(nbsp(formatCurrency(1500))).toBe("Rp 1.500");
  });
});

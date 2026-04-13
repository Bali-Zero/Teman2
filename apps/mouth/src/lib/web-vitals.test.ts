import { describe, it, expect } from "vitest";
import {
  formatMetricValue,
  getMetricRatingColor,
  INP_THRESHOLDS,
} from "./web-vitals";

describe("formatMetricValue", () => {
  it("formats CLS with 3 decimal places", () => {
    expect(formatMetricValue(0.123456, "CLS")).toBe("0.123");
    expect(formatMetricValue(0.1, "CLS")).toBe("0.100");
  });

  it("formats non-CLS metrics in ms (rounded)", () => {
    expect(formatMetricValue(1234.56, "LCP")).toBe("1235ms");
    expect(formatMetricValue(89.2, "TTFB")).toBe("89ms");
    expect(formatMetricValue(200, "INP")).toBe("200ms");
    expect(formatMetricValue(1800, "FCP")).toBe("1800ms");
  });
});

describe("getMetricRatingColor", () => {
  it("returns green for good rating", () => {
    expect(getMetricRatingColor("good")).toBe("text-green-500");
  });

  it("returns yellow for needs-improvement", () => {
    expect(getMetricRatingColor("needs-improvement")).toBe("text-yellow-500");
  });

  it("returns red for poor rating", () => {
    expect(getMetricRatingColor("poor")).toBe("text-red-500");
  });
});

describe("INP_THRESHOLDS", () => {
  it("defines good threshold at 200ms", () => {
    expect(INP_THRESHOLDS.good).toBe(200);
  });

  it("defines needs-improvement threshold at 500ms", () => {
    expect(INP_THRESHOLDS.needsImprovement).toBe(500);
  });
});

import { describe, it, expect } from "vitest";
import {
  getArticlePalette,
  CRITICAL_PALETTE,
  NEW_PALETTE,
  UPDATED_PALETTE,
  NEUTRAL_PALETTE,
} from "./article-palette";

describe("getArticlePalette (P1.5 state-driven accent)", () => {
  it("returns the red palette for critical items", () => {
    expect(
      getArticlePalette({ is_critical: true, detection_type: "NEW" }),
    ).toBe(CRITICAL_PALETTE);
  });

  it("critical wins over detection_type", () => {
    expect(
      getArticlePalette({ is_critical: true, detection_type: "UPDATED" }),
    ).toBe(CRITICAL_PALETTE);
  });

  it("returns the blue palette for NEW items", () => {
    expect(
      getArticlePalette({ is_critical: false, detection_type: "NEW" }),
    ).toBe(NEW_PALETTE);
    expect(getArticlePalette({ detection_type: "NEW" })).toBe(NEW_PALETTE);
  });

  it("returns the cyan palette for UPDATED items", () => {
    expect(
      getArticlePalette({ is_critical: false, detection_type: "UPDATED" }),
    ).toBe(UPDATED_PALETTE);
  });

  it("falls back to the neutral brand palette for unknown states", () => {
    expect(
      getArticlePalette({
        detection_type: "UNKNOWN" as unknown as "NEW",
      }),
    ).toBe(NEUTRAL_PALETTE);
  });
});

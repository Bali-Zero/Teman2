import { describe, expect, it } from "vitest";
import { matchesStatusFilter } from "./kanban-colors";

describe("matchesStatusFilter", () => {
  it("keeps unrecognized backend statuses visible in the Inquiry filter", () => {
    expect(matchesStatusFilter("legacy_unmapped_status", "inquiry")).toBe(true);
  });

  it("does not include an unrecognized status in another workflow filter", () => {
    expect(matchesStatusFilter("legacy_unmapped_status", "completed")).toBe(
      false,
    );
  });

  it("matches legacy aliases through their visible workflow column", () => {
    expect(matchesStatusFilter("request", "inquiry")).toBe(true);
    expect(matchesStatusFilter("done", "completed")).toBe(true);
  });
});

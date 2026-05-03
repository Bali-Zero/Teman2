import { describe, it, expect } from "vitest";
import { normalizeDashboardRole, VALID_ROLES } from "../dashboard-role";

describe("normalizeDashboardRole", () => {
  it("returns 'zero' when isAdmin is true regardless of role string", () => {
    expect(normalizeDashboardRole("member", true)).toBe("zero");
    expect(normalizeDashboardRole(undefined, true)).toBe("zero");
    expect(normalizeDashboardRole("tax", true)).toBe("zero");
  });

  it("returns matched role for valid lowercase strings", () => {
    expect(normalizeDashboardRole("team", false)).toBe("team");
    expect(normalizeDashboardRole("tax", false)).toBe("tax");
    expect(normalizeDashboardRole("marketing", false)).toBe("marketing");
    expect(normalizeDashboardRole("accounting", false)).toBe("accounting");
  });

  it("is case-insensitive", () => {
    expect(normalizeDashboardRole("TAX", false)).toBe("tax");
    expect(normalizeDashboardRole("Marketing", false)).toBe("marketing");
    expect(normalizeDashboardRole("ACCOUNTING", false)).toBe("accounting");
  });

  it("falls back to 'team' for unknown roles", () => {
    expect(normalizeDashboardRole("consultant", false)).toBe("team");
    expect(normalizeDashboardRole("", false)).toBe("team");
    expect(normalizeDashboardRole(undefined, false)).toBe("team");
  });

  it("exports VALID_ROLES containing all 5 roles", () => {
    expect(VALID_ROLES).toContain("zero");
    expect(VALID_ROLES).toContain("team");
    expect(VALID_ROLES).toContain("tax");
    expect(VALID_ROLES).toContain("marketing");
    expect(VALID_ROLES).toContain("accounting");
    expect(VALID_ROLES).toHaveLength(5);
  });
});

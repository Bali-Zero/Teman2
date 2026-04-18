import { describe, it, expect, vi } from "vitest";

vi.mock("next/navigation", () => ({
  permanentRedirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
}));

import LegacyLoginRedirect from "./page";

describe("LegacyLoginRedirect", () => {
  it("redirects to /portal/login-upgraded without redirect param", async () => {
    await expect(LegacyLoginRedirect({ searchParams: {} })).rejects.toThrow(
      "REDIRECT:/portal/login-upgraded",
    );
  });
  it("preserves safe redirect param", async () => {
    await expect(
      LegacyLoginRedirect({ searchParams: { redirect: "/portal/dashboard" } }),
    ).rejects.toThrow(
      "REDIRECT:/portal/login-upgraded?redirect=%2Fportal%2Fdashboard",
    );
  });
  it("strips unsafe protocol-relative redirect", async () => {
    await expect(
      LegacyLoginRedirect({ searchParams: { redirect: "//evil.com" } }),
    ).rejects.toThrow("REDIRECT:/portal/login-upgraded");
  });
  it("strips unsafe javascript: redirect", async () => {
    await expect(
      LegacyLoginRedirect({
        searchParams: { redirect: "javascript:alert(1)" },
      }),
    ).rejects.toThrow("REDIRECT:/portal/login-upgraded");
  });
  it("allows /workspace/ redirect", async () => {
    await expect(
      LegacyLoginRedirect({ searchParams: { redirect: "/workspace/kita" } }),
    ).rejects.toThrow(
      "REDIRECT:/portal/login-upgraded?redirect=%2Fworkspace%2Fkita",
    );
  });
});

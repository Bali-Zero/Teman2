import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { PortalUsageTracker } from "./PortalUsageTracker";

const pathname = vi.hoisted(() => ({ value: "/portal" }));
const trackPage = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));
vi.mock("@/lib/api", () => ({
  api: {
    getUserProfile: () => ({ role: "client" }),
    getPortalImpersonation: () => null,
  },
}));
vi.mock("@/lib/portal-analytics", () => ({ trackPortalPage: trackPage }));

beforeEach(() => {
  trackPage.mockClear();
  pathname.value = "/portal";
});
describe("authenticated portal page consumer", () => {
  it("tracks first entry and navigation, not ordinary rerenders", () => {
    const { rerender } = render(<PortalUsageTracker />);
    expect(trackPage).toHaveBeenCalledTimes(1);
    rerender(<PortalUsageTracker />);
    expect(trackPage).toHaveBeenCalledTimes(1);
    pathname.value = "/portal/vault";
    rerender(<PortalUsageTracker />);
    expect(trackPage).toHaveBeenCalledTimes(2);
    expect(trackPage.mock.calls[1][0]).toBe("/portal/vault");
    expect(trackPage.mock.calls[1][1]()).toEqual({
      role: "client",
      impersonating: false,
    });
  });
});

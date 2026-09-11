import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

import { RouteChangeTracker } from "./RouteChangeTracker";

const usePathnameMock = vi.fn<() => string>();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
}));

type GtagFn = (...args: unknown[]) => void;

describe("RouteChangeTracker", () => {
  let gtag: ReturnType<typeof vi.fn<GtagFn>>;

  beforeEach(() => {
    gtag = vi.fn<GtagFn>();
    (window as typeof window & { gtag?: GtagFn }).gtag = gtag;
  });

  afterEach(() => {
    delete (window as typeof window & { gtag?: unknown }).gtag;
    vi.clearAllMocks();
  });

  it("does NOT fire on the initial load (already tracked by gtag config)", () => {
    usePathnameMock.mockReturnValue("/kbli/56303");
    render(<RouteChangeTracker />);
    expect(gtag).not.toHaveBeenCalled();
  });

  it("fires page_view on client-side path change only", () => {
    usePathnameMock.mockReturnValue("/kbli/56303");
    const { rerender } = render(<RouteChangeTracker />);

    usePathnameMock.mockReturnValue("/kbli/55203");
    rerender(<RouteChangeTracker />);

    expect(gtag).toHaveBeenCalledTimes(1);
    expect(gtag).toHaveBeenCalledWith(
      "event",
      "page_view",
      expect.objectContaining({ page_path: "/kbli/55203" }),
    );
  });

  it("never sends a credential-bearing query string as page_location", () => {
    // Portal audit L-GA (2026-09-11): the raw href reached
    // google-analytics.com/g/collect with the single-use token in `dl=`.
    window.history.replaceState({}, "", "/portal/magic?token=LEAKME");
    usePathnameMock.mockReturnValue("/portal/magic");
    const { rerender } = render(<RouteChangeTracker />);

    window.history.replaceState({}, "", "/portal/register?token=LEAKMETOO");
    usePathnameMock.mockReturnValue("/portal/register");
    rerender(<RouteChangeTracker />);

    expect(gtag).toHaveBeenCalledTimes(1);
    const payload = gtag.mock.calls[0][2] as { page_location: string };
    expect(payload.page_location).not.toContain("LEAKMETOO");
    expect(payload.page_location).toContain("/portal/register");
  });

  it("is a no-op when gtag is not loaded", () => {
    delete (window as typeof window & { gtag?: unknown }).gtag;
    usePathnameMock.mockReturnValue("/a");
    const { rerender } = render(<RouteChangeTracker />);
    usePathnameMock.mockReturnValue("/b");
    expect(() => rerender(<RouteChangeTracker />)).not.toThrow();
  });
});

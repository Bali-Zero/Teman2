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

  it("is a no-op when gtag is not loaded", () => {
    delete (window as typeof window & { gtag?: unknown }).gtag;
    usePathnameMock.mockReturnValue("/a");
    const { rerender } = render(<RouteChangeTracker />);
    usePathnameMock.mockReturnValue("/b");
    expect(() => rerender(<RouteChangeTracker />)).not.toThrow();
  });
});

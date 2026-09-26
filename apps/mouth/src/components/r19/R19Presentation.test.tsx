import { renderToStaticMarkup } from "react-dom/server";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { R19Presentation } from "./R19Presentation";
import { MobileNav } from "@/app/v2/_components/MobileNav";

const route = vi.hoisted(() => ({ pathname: "/news" }));
vi.mock("next/navigation", () => ({ usePathname: () => route.pathname }));
vi.mock("@balizero/core/analytics", () => ({ trackFunnelEvent: vi.fn() }));
vi.mock("@balizero/core/auth", () => ({
  getOrCreateSessionId: () => "test-session",
}));
vi.stubGlobal(
  "matchMedia",
  vi.fn(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
);
afterEach(cleanup);
const child = (
  <MobileNav items={[{ label: "Home", href: "/" }]} funnel="home" />
);

describe("R19 presentation and portal", () => {
  it.each([
    ["/", 2],
    ["/news", 2],
    ["/property", 0],
    ["/v2", 0],
    ["/property/eligibility", 0],
  ])(
    "discovers display fonts in server HTML only on selected route %s",
    (pathname, count) => {
      route.pathname = pathname;
      const document = new DOMParser().parseFromString(
        renderToStaticMarkup(
          <R19Presentation>
            <p>Fixture</p>
          </R19Presentation>,
        ),
        "text/html",
      );
      const preloads = [
        ...document.querySelectorAll('link[rel="preload"][as="font"]'),
      ];
      expect(preloads).toHaveLength(count);
      if (count) {
        expect(preloads.map((link) => link.getAttribute("href"))).toEqual([
          "/fonts/fraunces-r19-latin.woff2",
          "/fonts/manrope-r19-latin.woff2",
        ]);
        expect(
          preloads.every(
            (link) => link.getAttribute("crossorigin") === "anonymous",
          ),
        ).toBe(true);
      }
    },
  );

  // Dormant foundation: this asserts the R19-aware MobileNav drawer, which lands with the
  // cutover change to app/v2/_components/MobileNav.tsx. Un-skip it in that PR.
  it.skip("applies the selected theme to a drawer outside the page wrapper", async () => {
    route.pathname = "/news";
    const { container } = render(<R19Presentation>{child}</R19Presentation>);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const dialog = await screen.findByRole("dialog");
    expect(container.contains(dialog)).toBe(false);
    expect(dialog.style.getPropertyValue("--nav-bg")).toBe("#F7F4EE");
    expect(dialog.style.getPropertyValue("--text-primary")).toBe("#1D2C3B");
  });
  it("removes the presentation on navigation to the protected property landing", () => {
    route.pathname = "/property/example";
    const { container, rerender } = render(
      <R19Presentation>{child}</R19Presentation>,
    );
    expect(container.querySelector('[data-presentation="r19"]')).not.toBeNull();
    route.pathname = "/property";
    rerender(<R19Presentation>{child}</R19Presentation>);
    expect(container.querySelector('[data-presentation="r19"]')).toBeNull();
    expect(screen.getByRole("button", { name: "Open menu" }).style.color).toBe(
      "rgb(255, 255, 255)",
    );
  });
});

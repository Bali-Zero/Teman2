import { render, screen } from "@testing-library/react";
import GarudaVoaLayout from "./layout";

/**
 * The team-lead flag (2026-08-25): measured on this branch, GARUDA_PUBLIC_ENABLED
 * appeared three times in apps/mouth, all prose (test descriptions + a docblock) —
 * no frontend code read it, so the funnel rendered in full for anyone with the URL
 * despite the mandate's "running in PRODUCTION behind the flag". This file pins the
 * layout-level enforcement; the fail-closed parsing itself is pinned in flag.test.ts
 * (moved there 2026-08-25 second round — see flag.ts's docblock for why the parsing
 * function cannot live as a named export inside layout.tsx).
 */

const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}));

describe("GarudaVoaLayout — server-side gate", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;
  beforeEach(() => {
    notFoundMock.mockClear();
  });
  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
  });

  it("404s when the flag is unset", () => {
    delete process.env.GARUDA_PUBLIC_ENABLED;
    expect(() =>
      render(
        <GarudaVoaLayout>
          <div data-testid="voa-content" />
        </GarudaVoaLayout>,
      ),
    ).toThrow("NEXT_NOT_FOUND");
    expect(notFoundMock).toHaveBeenCalled();
  });

  it('404s when the flag is the string "false"', () => {
    process.env.GARUDA_PUBLIC_ENABLED = "false";
    expect(() =>
      render(
        <GarudaVoaLayout>
          <div data-testid="voa-content" />
        </GarudaVoaLayout>,
      ),
    ).toThrow("NEXT_NOT_FOUND");
  });

  it('renders children when the flag is exactly "true"', () => {
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    render(
      <GarudaVoaLayout>
        <div data-testid="voa-content" />
      </GarudaVoaLayout>,
    );
    expect(screen.getByTestId("voa-content")).toBeInTheDocument();
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  // R19 skin: the funnel wears the
  // [data-theme="operative-light"][data-product="my"] tokens (paper ground
  // #f7f4ee, ink type, copper #a44b36 for "needs you"), via a wrapper this
  // layout owns — not the shared /visa navy+red skin, and not the anthracite
  // ground the DELIBERA fase 2 (a) flip put here between 2026-08 and
  // 2026-09-21.
  //
  // This row is the whole reason the flip is one line. `voa-r19.css` names
  // no theme in its selectors, and `voa-contrast.computed.guard.test.tsx`
  // parses the theme back OUT of layout.tsx instead of naming one — so the
  // wrapper below is the single declaration of the funnel's ground, and it
  // is pinned here.
  it("wraps children in the R19 wrapper (data-product=my, data-theme=operative-light)", () => {
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    const { container } = render(
      <GarudaVoaLayout>
        <div data-testid="voa-content" />
      </GarudaVoaLayout>,
    );
    const wrapper = container.querySelector('[data-garuda-voa="r19"]');
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveAttribute("data-product", "my");
    expect(wrapper).toHaveAttribute("data-theme", "operative-light");
    expect(wrapper?.contains(screen.getByTestId("voa-content"))).toBe(true);
  });
});

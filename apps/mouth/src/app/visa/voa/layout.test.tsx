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

  // R19 skin (GARUDA VOA DELIBERA fase 2 (a)): the funnel wears the
  // [data-theme="operative-dark"][data-product="my"] tokens (anthracite
  // ground, design-A/refutation-measured), via a wrapper this layout owns —
  // not the shared /visa navy+red skin, and not the paper ground this
  // surface shipped with before the flip.
  it("wraps children in the R19 wrapper (data-product=my, data-theme=operative-dark)", () => {
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    const { container } = render(
      <GarudaVoaLayout>
        <div data-testid="voa-content" />
      </GarudaVoaLayout>,
    );
    const wrapper = container.querySelector('[data-garuda-voa="r19"]');
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveAttribute("data-product", "my");
    expect(wrapper).toHaveAttribute("data-theme", "operative-dark");
    expect(wrapper?.contains(screen.getByTestId("voa-content"))).toBe(true);
  });
});

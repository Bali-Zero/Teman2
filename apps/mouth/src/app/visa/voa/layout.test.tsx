import { render, screen } from "@testing-library/react";
import GarudaVoaLayout, { isGarudaVoaPublicEnabled } from "./layout";

/**
 * The team-lead flag (2026-08-25): measured on this branch, GARUDA_PUBLIC_ENABLED
 * appeared three times in apps/mouth, all prose (test descriptions + a docblock) —
 * no frontend code read it, so the funnel rendered in full for anyone with the URL
 * despite the mandate's "running in PRODUCTION behind the flag". This file pins the
 * fix in both directions, plus the fail-closed parsing (unset/"false"/typo = dark).
 */

const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}));

describe("isGarudaVoaPublicEnabled — fail-closed parsing", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;
  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
  });

  it.each([
    [undefined, false],
    ["", false],
    ["false", false],
    ["False", false],
    ["0", false],
    ["typo", false],
    ["true", true],
    ["TRUE", true],
    ["  true  ", true],
  ])("GARUDA_PUBLIC_ENABLED=%p -> %p", (value, expected) => {
    if (value === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = value;
    expect(isGarudaVoaPublicEnabled()).toBe(expected);
  });
});

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
});

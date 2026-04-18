import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { PrimeGate } from "../PrimeGate";

vi.mock("../hooks/useBrowserSupport", () => ({
  useBrowserSupport: vi.fn(),
}));
import { useBrowserSupport } from "../hooks/useBrowserSupport";

describe("PrimeGate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a skeleton while detection is loading", () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: true,
      supported: false,
      chromium: false,
      webgl2: false,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    expect(screen.queryByTestId("map")).toBeNull();
    expect(screen.getByTestId("prime-gate-loading")).toBeInTheDocument();
  });

  it("renders children when supported", () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: false,
      supported: true,
      chromium: true,
      webgl2: true,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });

  it("shows a fallback message on unsupported browser", () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: false,
      supported: false,
      chromium: false,
      webgl2: true,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    expect(screen.queryByTestId("map")).toBeNull();
    expect(
      screen.getByRole("heading", { name: /prime requires/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /continue anyway/i }),
    ).toBeInTheDocument();
  });

  it("Continue anyway reveals children", async () => {
    (useBrowserSupport as ReturnType<typeof vi.fn>).mockReturnValue({
      loading: false,
      supported: false,
      chromium: false,
      webgl2: true,
      isMobile: false,
    });
    render(
      <PrimeGate>
        <div data-testid="map">MAP</div>
      </PrimeGate>,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /continue anyway/i }),
    );
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });
});

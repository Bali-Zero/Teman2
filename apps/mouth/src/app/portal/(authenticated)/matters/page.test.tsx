import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockUsePortalMatters } = vi.hoisted(() => ({
  mockUsePortalMatters: vi.fn(),
}));

vi.mock("@/hooks", () => ({
  usePortalMatters: mockUsePortalMatters,
}));

vi.mock("@/components/portal", () => ({
  PortalListSkeleton: ({ count }: { count?: number }) => (
    <div data-testid="portal-list-skeleton">{count}</div>
  ),
}));

import PortalMattersPage from "./page";

const MATTERS = {
  matters: [
    {
      id: 9,
      title: "Company Setup",
      type: "company" as const,
      progress: 60,
      pending_docs: ["Company registry"],
      next_deadline: null,
      next_step: "Review filing date",
    },
  ],
};

describe("PortalMattersPage", () => {
  it("renders the day masthead and matter cards with semantic-token styling (WS3)", () => {
    mockUsePortalMatters.mockReturnValue({
      data: MATTERS,
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = render(<PortalMattersPage />);

    // Day masthead: copper rule + Cormorant serif headline in --tx-pure
    // (replaces lux-text-gradient, which is white-on-white on paper).
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Your matters");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(container.querySelector(".lux-text-gradient")).toBeNull();
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Matter card content renders.
    expect(screen.getByText("Company Setup")).toBeInTheDocument();

    // "Open" link: copper text step with AA fallback + ink hover (was
    // --bz-copper at 2.57:1 on paper + hover:text-white, invisible on day).
    const openLink = screen.getByRole("link", { name: /Open/ });
    expect(openLink).toHaveAttribute("href", "/portal/matters/9");
    expect(openLink.className).toContain("--bz-copper-text");
    expect(openLink.className).toContain("hover:text-[var(--tx-pure)]");
    expect(openLink.className).not.toContain("hover:text-white");

    // Drain guard: no hardcoded hex colors anywhere in the page output.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("keeps the masthead on the loading and error states", () => {
    mockUsePortalMatters.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });
    const { unmount } = render(<PortalMattersPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Your matters",
    );
    expect(screen.getByTestId("portal-list-skeleton")).toBeInTheDocument();
    unmount();

    mockUsePortalMatters.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
    });
    render(<PortalMattersPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Your matters",
    );
    expect(screen.getByText("Unable to load matters")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("renders the empty state when there are no open matters", () => {
    mockUsePortalMatters.mockReturnValue({
      data: { matters: [] },
      isLoading: false,
      isError: false,
      error: null,
    });
    render(<PortalMattersPage />);
    expect(screen.getByText("No open matters")).toBeInTheDocument();
  });
});

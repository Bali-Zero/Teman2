import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockUseQuery, mockRefetch } = vi.hoisted(() => ({
  mockUseQuery: vi.fn(),
  mockRefetch: vi.fn(),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: mockUseQuery,
}));

vi.mock("@/lib/api", () => ({
  api: { request: vi.fn() },
}));

import PortalFamilyPage from "./page";

// Synthetic fixture only — no real client data.
const FAMILY = {
  adults: [
    {
      id: 1,
      full_name: "Ada Example",
      relationship: "Spouse",
      date_of_birth: "1990-05-10",
      is_adult: true,
      nationality: "Italian",
      passport_number: "YA1234567",
      passport_expiry: "2030-01-01",
      visa_type: "KITAS",
      visa_expiry: "2027-06-01",
      email: null,
      phone: null,
    },
  ],
  minors: [
    {
      id: 2,
      full_name: "Ben Example",
      relationship: "Child",
      date_of_birth: "2018-03-15",
      is_adult: false,
      nationality: null,
      passport_number: "YB7654321",
      passport_expiry: "2029-01-01",
      visa_type: null,
      visa_expiry: null,
      email: null,
      phone: null,
    },
  ],
};

function mockLoaded(data: unknown = FAMILY) {
  mockUseQuery.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    error: null,
    refetch: mockRefetch,
  });
}

describe("PortalFamilyPage", () => {
  it("renders the day masthead and token-driven member cards (WS3 slice 8)", () => {
    mockLoaded();
    const { container } = render(<PortalFamilyPage />);

    // Day masthead: copper rule + Cormorant serif headline in --tx-pure.
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Family");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Member cards read theme tokens, not the old dark rgba glass.
    expect(container.innerHTML).toContain("var(--bz-card)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.01)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");

    // Drain guard: no hardcoded hex colors anywhere in the page output.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("splits adults/minors and stamps relationship chips in daylight copper", () => {
    mockLoaded();
    render(<PortalFamilyPage />);

    expect(screen.getByText(/Adults \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/Minors \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("Ada Example")).toBeInTheDocument();
    expect(screen.getByText("Ben Example")).toBeInTheDocument();

    // Relationship chips: small copper text on the AA daylight step.
    for (const chip of [
      screen.getByText("Spouse"),
      screen.getByText("Child"),
    ]) {
      expect(chip.style.color).toBe(
        "var(--bz-copper-text, var(--tx-secondary))",
      );
    }
  });

  it("re-tokenizes the destructive alert to --state-danger on error", () => {
    mockUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      refetch: mockRefetch,
    });
    render(<PortalFamilyPage />);

    const alert = screen.getByRole("alert");
    expect(alert.style.background).toContain("var(--state-danger) 8%");
    expect(alert.style.borderColor).toContain("var(--state-danger) 30%");
    expect(alert.style.color).toBe("var(--bz-text-1)");
    expect(screen.getByText("Unable to load family")).toBeInTheDocument();
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "We could not verify your family records. Check your connection and try again.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mockRefetch).toHaveBeenCalledOnce();
  });

  it("renders the empty-state guidance when no members are on file", () => {
    mockLoaded({ adults: [], minors: [] });
    render(<PortalFamilyPage />);

    expect(screen.getByText("No family members on file")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Family",
    );
  });
});

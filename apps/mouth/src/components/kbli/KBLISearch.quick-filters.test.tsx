import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { KBLISearch } from "./KBLISearch";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const search = vi.fn();
vi.mock("@/lib/api/kbli.api", () => ({
  kbliApi: { search: (q: string) => search(q) },
  apiPmaStatusLabel: () => "Open",
  isApiPmaVerdictVerified: () => true,
}));
vi.mock("@/lib/analytics", () => ({ trackKBLISearch: vi.fn() }));

const FILTERS = ["Restaurant", "Tech"];

describe("KBLISearch quick filters", () => {
  beforeEach(() => {
    push.mockReset();
    search.mockReset();
    search.mockResolvedValue([
      {
        code: "56101",
        title: "Restoran",
        description: "Restaurants",
        risk_category: "MR",
      },
    ]);
  });

  it("writes the chip term into the search input", () => {
    render(<KBLISearch quickFilters={FILTERS} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Search Restaurant" }));
    expect(input.value).toBe("Restaurant");
  });

  it("actually runs the search for the chip term", async () => {
    render(<KBLISearch quickFilters={FILTERS} />);
    fireEvent.click(screen.getByRole("button", { name: "Search Tech" }));

    await waitFor(() => expect(search).toHaveBeenCalledWith("Tech"), {
      timeout: 2000,
    });
    expect(await screen.findByText("Restoran")).toBeInTheDocument();
  });

  it("replaces a previous term instead of appending to it", () => {
    render(<KBLISearch quickFilters={FILTERS} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "villa" } });
    fireEvent.click(screen.getByRole("button", { name: "Search Tech" }));
    expect(input.value).toBe("Tech");
  });

  it("marks the active chip as pressed, and only that one", () => {
    render(<KBLISearch quickFilters={FILTERS} />);
    fireEvent.click(screen.getByRole("button", { name: "Search Restaurant" }));

    expect(
      screen.getByRole("button", { name: "Search Restaurant" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Search Tech" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("renders no chip row when the caller passes none", () => {
    render(<KBLISearch />);
    expect(screen.queryByText("Quick:")).not.toBeInTheDocument();
  });
});

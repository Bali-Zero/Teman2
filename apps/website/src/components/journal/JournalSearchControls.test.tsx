import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JournalSearchControls } from "./JournalSearchControls";

describe("archive controls", () => {
  it("removes one filter without losing the other and resets pagination", () => {
    render(
      <JournalSearchControls
        query={{ q: "leasehold", category: "property", page: 3 }}
        status="ready"
        count={12}
        total={30}
      />,
    );
    expect(
      screen.getByRole("link", { name: "Remove search: leasehold" }),
    ).toHaveAttribute("href", "/news?category=property#latest-stories-title");
    expect(
      screen.getByRole("link", { name: "Remove topic: Property" }),
    ).toHaveAttribute("href", "/news?q=leasehold#latest-stories-title");
    expect(screen.getByRole("searchbox")).toHaveValue("leasehold");
  });
  it("shows native navigation pending and restores the form on browser return", () => {
    render(<JournalSearchControls count={12} status="ready" />);
    fireEvent.submit(screen.getByRole("search"));
    expect(screen.getByRole("button", { name: /Searching/ })).toBeDisabled();
    expect(screen.getByRole("search")).toHaveAttribute(
      "action",
      "/news#latest-stories-title",
    );
    fireEvent(window, new Event("pageshow"));
    expect(screen.getByRole("button", { name: /Search/ })).toBeEnabled();
  });
  it("keeps recovery controls available without showing a false count on failure", () => {
    render(
      <JournalSearchControls
        query={{ q: "leasehold" }}
        count={0}
        total={0}
        status="unavailable"
      />,
    );
    expect(screen.getByText(/Search results are unavailable/)).toBeVisible();
    expect(screen.queryByText(/0 matching/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Clear search and filters" }),
    ).toBeVisible();
  });
});

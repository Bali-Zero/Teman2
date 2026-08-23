import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RouteComparator } from "./RouteComparator";

describe("RouteComparator", () => {
  it("renders the three column headings with their text labels", () => {
    render(<RouteComparator />);

    expect(screen.getByText("Deposit route")).toBeInTheDocument();
    expect(screen.getByText("Property route")).toBeInTheDocument();
    expect(screen.getByText("Senior route (55+)")).toBeInTheDocument();
  });

  it("renders an aria-hidden icon next to each column heading", () => {
    const { container } = render(<RouteComparator />);

    const headings = container.querySelectorAll(
      "th > span > svg[aria-hidden='true']",
    );
    expect(headings.length).toBe(3);
  });

  it("does not remove the accessible column text when icons are present", () => {
    render(<RouteComparator highlight />);

    const depositHeading = screen.getByText("Deposit route").closest("th");
    expect(depositHeading).toBeInTheDocument();
    const icon = depositHeading?.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });
});

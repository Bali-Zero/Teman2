import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TimelineView } from "./TimelineView";

describe("TimelineView", () => {
  it("renders owner chips with their text labels", () => {
    render(
      <TimelineView
        horizon="exploring"
        location="in_indonesia"
        route="deposit"
        product="E33"
      />,
    );

    expect(screen.getAllByText("You").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Bali Zero").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Imigrasi")).toBeInTheDocument();
  });

  it("renders an aria-hidden icon inside every owner chip", () => {
    const { container } = render(
      <TimelineView
        horizon="exploring"
        location="in_indonesia"
        route="deposit"
        product="E33"
      />,
    );

    const chips = container.querySelectorAll("span > svg[aria-hidden='true']");
    expect(chips.length).toBeGreaterThanOrEqual(3);
  });

  it("keeps the text label as the accessible name and does not duplicate it via icon", () => {
    render(
      <TimelineView
        horizon="asap"
        location="abroad"
        route="property"
        product="E33"
      />,
    );

    const youChips = screen.getAllByText("You");
    expect(youChips.length).toBeGreaterThanOrEqual(1);
    const firstYouChip = youChips[0]!.closest("span");
    expect(firstYouChip).toBeInTheDocument();
    const icon = firstYouChip?.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });
});

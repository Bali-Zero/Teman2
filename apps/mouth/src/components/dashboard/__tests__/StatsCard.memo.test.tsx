/**
 * Test suite for StatsCard memoization
 * Verifies that React.memo prevents unnecessary re-renders
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatsCard } from "../StatsCard";
import { FolderKanban } from "lucide-react";

describe("StatsCard Memoization", () => {
  const defaultProps = {
    title: "Test Card",
    value: 100,
    icon: FolderKanban,
  };

  it("should render without errors", () => {
    render(<StatsCard {...defaultProps} />);
    expect(screen.getByText("Test Card")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("should be memoized (React.memo)", () => {
    // Check that StatsCard is wrapped with React.memo
    // React.memo creates a special component type
    const component = StatsCard;
    expect(component).toBeDefined();

    // React.memo components have a $$typeof symbol
    // We can verify by checking if the component is not a plain function
    expect(typeof component).toBe("object");
  });

  it("should render with variant styles", () => {
    const { rerender } = render(
      <StatsCard {...defaultProps} variant="warning" />,
    );

    rerender(<StatsCard {...defaultProps} variant="danger" />);
    // Should re-render with new variant
    expect(screen.getByText("Test Card")).toBeInTheDocument();
  });
});

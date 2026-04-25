import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardStatCard } from "../DashboardStatCard";

describe("DashboardStatCard", () => {
  const baseProps = {
    icon: "📁",
    value: 24,
    label: "Active Cases",
    trend: "▲ +3",
    colorVariant: "green" as const,
  };

  it("renders the value", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("24")).toBeInTheDocument();
  });

  it("renders the label", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("Active Cases")).toBeInTheDocument();
  });

  it("renders the trend text", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("▲ +3")).toBeInTheDocument();
  });

  it("renders the icon", () => {
    render(<DashboardStatCard {...baseProps} />);
    expect(screen.getByText("📁")).toBeInTheDocument();
  });

  it("applies correct color class for each variant", () => {
    const { container, rerender } = render(
      <DashboardStatCard {...baseProps} colorVariant="red" />,
    );
    expect(container.firstChild).toHaveClass("glass-red");

    rerender(<DashboardStatCard {...baseProps} colorVariant="yellow" />);
    expect(container.firstChild).toHaveClass("glass-yellow");

    rerender(<DashboardStatCard {...baseProps} colorVariant="blue" />);
    expect(container.firstChild).toHaveClass("glass-blue");
  });

  it("renders string values", () => {
    render(<DashboardStatCard {...baseProps} value="$48K" />);
    expect(screen.getByText("$48K")).toBeInTheDocument();
  });
});

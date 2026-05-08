import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ComparisonTable } from "./ComparisonTable";

vi.mock("framer-motion", () => ({
  motion: {
    tr: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <tr {...props}>{children}</tr>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

describe("ComparisonTable", () => {
  it("renders empty states for missing data", () => {
    const { rerender } = render(
      <ComparisonTable title="Entity Comparison" items={[]} />,
    );

    expect(screen.getByText("No comparison data available")).toBeInTheDocument();

    rerender(
      <ComparisonTable
        title="Entity Comparison"
        items={[{ id: "pma", name: "PT PMA" }]}
      />,
    );

    expect(screen.getByText("No features to compare")).toBeInTheDocument();
  });

  it("renders simple MDX-style comparisons with missing values", () => {
    render(
      <ComparisonTable
        title="Visa Routes"
        subtitle="Quick fit"
        items={[
          {
            name: "Investor",
            subtitle: "Long stay",
            highlight: true,
            values: { Duration: "2 years", Renewal: "Yes" },
          },
          {
            name: "Business",
            values: { Duration: "60 days" },
          },
        ]}
      />,
    );

    expect(screen.getByText("Visa Routes")).toBeInTheDocument();
    expect(screen.getByText("Quick fit")).toBeInTheDocument();
    expect(screen.getByText("Investor")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
    expect(screen.getByText("Renewal")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows recommendations, differences-only filtering, and category collapse", () => {
    render(
      <ComparisonTable
        title="Company Setup"
        recommendationText="Best fit: PT PMA"
        items={[
          {
            id: "pma",
            name: "PT PMA",
            color: "green",
            recommended: true,
            learnMoreUrl: "/pma",
          },
          { id: "pt", name: "Local PT", color: "blue" },
        ]}
        features={[
          {
            id: "ownership",
            name: "Foreign ownership",
            category: "Eligibility",
            values: { pma: true, pt: false },
            important: true,
          },
          {
            id: "documents",
            name: "Document package",
            category: "Eligibility",
            values: { pma: "Akta + NIB", pt: "Akta + NIB" },
          },
          {
            id: "visa",
            name: "Investor visa",
            category: "Immigration",
            values: { pma: "Available", pt: null },
          },
        ]}
        showDifferencesOnly
      />,
    );

    expect(screen.getByText("Best fit: PT PMA")).toBeInTheDocument();
    expect(screen.getByText("Foreign ownership")).toBeInTheDocument();
    expect(screen.getByText("Investor visa")).toBeInTheDocument();
    expect(screen.queryByText("Document package")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /learn more about pt pma/i })).toHaveAttribute(
      "href",
      "/pma",
    );

    fireEvent.click(screen.getByRole("button", { name: /differences only/i }));

    expect(screen.getByText("Document package")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Eligibility" }));
    expect(screen.queryByText("Foreign ownership")).not.toBeInTheDocument();
    expect(screen.queryByText("Document package")).not.toBeInTheDocument();
    expect(screen.getByText("Investor visa")).toBeInTheDocument();
  });
});

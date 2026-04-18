import * as React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrustBadges } from "./TrustBadges";

describe("TrustBadges", () => {
  it("renders default stats as a list", () => {
    render(<TrustBadges />);
    const list = screen.getByRole("list", { name: /bali zero trust signals/i });
    expect(list).toBeInTheDocument();
    expect(list.querySelectorAll("li").length).toBeGreaterThanOrEqual(3);
  });

  it("renders custom stats", () => {
    render(
      <TrustBadges
        stats={[
          { value: "10/10", label: "Test stat", hint: "unit" },
        ]}
      />,
    );
    expect(screen.getByText("10/10")).toBeInTheDocument();
    expect(screen.getByText(/test stat/i)).toBeInTheDocument();
    expect(screen.getByText(/unit/i)).toBeInTheDocument();
  });
});

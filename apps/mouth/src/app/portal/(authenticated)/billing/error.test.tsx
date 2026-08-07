import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BillingError from "./error";

describe("BillingError", () => {
  it("keeps unexpected error details off the client surface", () => {
    render(
      <BillingError
        error={new Error("synthetic-private-backend-detail")}
        reset={vi.fn()}
      />,
    );

    expect(
      screen.getByText("We couldn't load your billing data. Please try again."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("synthetic-private-backend-detail"),
    ).not.toBeInTheDocument();
  });

  it("retries through the supplied boundary reset", () => {
    const reset = vi.fn();
    render(<BillingError error={new Error("synthetic")} reset={reset} />);

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(reset).toHaveBeenCalledOnce();
  });
});

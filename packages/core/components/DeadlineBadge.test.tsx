import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { DeadlineBadge } from "./DeadlineBadge";

describe("DeadlineBadge", () => {
  it("renders 'in Xd' when deadline is future", () => {
    const future = new Date(Date.now() + 5 * 86400_000);
    const { getByText } = render(<DeadlineBadge date={future} />);
    expect(getByText(/in 5d/)).toBeTruthy();
  });

  it("renders 'overdue' when deadline passed", () => {
    const past = new Date(Date.now() - 3 * 86400_000);
    const { getByText } = render(<DeadlineBadge date={past} />);
    expect(getByText(/overdue/i)).toBeTruthy();
  });

  it("maps days-left to status color", () => {
    const in2d = new Date(Date.now() + 2 * 86400_000);
    const { container } = render(<DeadlineBadge date={in2d} />);
    const fill = container.querySelector("circle[data-role='fill']");
    expect(fill?.getAttribute("stroke")).toBe("var(--color-status-danger)");
  });
});

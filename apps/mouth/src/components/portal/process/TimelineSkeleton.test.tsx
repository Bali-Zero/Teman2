import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TimelineSkeleton } from "./TimelineSkeleton";

describe("TimelineSkeleton", () => {
  it("renders 3 <li> rows by default", () => {
    render(<TimelineSkeleton />);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("renders N rows when count is provided", () => {
    render(<TimelineSkeleton count={5} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });

  it("renders 0 rows when count=0 (still renders the list container)", () => {
    render(<TimelineSkeleton count={0} />);
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    // container still present
    expect(
      screen.getByRole("list", { name: /loading timeline/i }),
    ).toBeInTheDocument();
  });

  it("exposes aria-label on the list container", () => {
    render(<TimelineSkeleton count={2} />);
    const list = screen.getByRole("list", { name: /loading timeline/i });
    expect(list.tagName.toLowerCase()).toBe("ul");
    expect(list.getAttribute("aria-label")).toBe("Loading timeline");
  });
});

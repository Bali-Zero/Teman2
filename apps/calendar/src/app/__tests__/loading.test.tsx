import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Loading from "../loading";

// Mock lucide-react
vi.mock("lucide-react", () => ({
  RefreshCw: (props: Record<string, unknown>) => (
    <svg data-testid="refresh-icon" {...props} />
  ),
}));

describe("Calendar Loading Page", () => {
  it("renders without crashing", () => {
    const { container } = render(<Loading />);
    expect(container.firstChild).toBeTruthy();
  });

  it("renders a spinning indicator", () => {
    const { container } = render(<Loading />);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeTruthy();
  });
});

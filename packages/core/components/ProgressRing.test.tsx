import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ProgressRing } from "./ProgressRing";

describe("ProgressRing", () => {
  it("renders a circular ring at given percent", () => {
    const { container } = render(<ProgressRing percent={66} />);
    const circle = container.querySelector("circle[data-role='fill']");
    expect(circle).toBeTruthy();
    const dasharray = circle?.getAttribute("stroke-dasharray");
    const dashoffset = circle?.getAttribute("stroke-dashoffset");
    expect(dasharray).toBeTruthy();
    expect(Number(dashoffset)).toBeGreaterThan(0);
  });

  it("clamps to [0, 100]", () => {
    const { container } = render(<ProgressRing percent={150} />);
    const label = container.querySelector("[data-role='label']");
    expect(label?.textContent).toBe("100%");
  });

  it("uses status color tokens", () => {
    const { container } = render(<ProgressRing percent={30} status="danger" />);
    const circle = container.querySelector("circle[data-role='fill']");
    expect(circle?.getAttribute("stroke")).toBe("var(--color-status-danger)");
  });
});

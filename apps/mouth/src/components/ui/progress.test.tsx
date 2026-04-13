import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Progress } from "./progress";

describe("Progress", () => {
  it("renders a progress bar element", () => {
    const { container } = render(<Progress value={50} />);
    const root = container.firstChild as HTMLElement;
    expect(root).toBeTruthy();
    expect(root.className).toContain("rounded-full");
    expect(root.className).toContain("overflow-hidden");
  });

  it("renders with default 0% when no value", () => {
    const { container } = render(<Progress />);
    const root = container.firstChild as HTMLElement;
    expect(root).toBeTruthy();
  });

  it("applies custom className", () => {
    const { container } = render(
      <Progress value={50} className="h-2 my-custom" />,
    );
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("my-custom");
  });

  it("applies indicator className", () => {
    const { container } = render(
      <Progress value={75} indicatorClassName="bg-green-500" />,
    );
    // The indicator is a child element
    const indicator = container.querySelector(
      "[class*='bg-green-500']",
    );
    expect(indicator).toBeTruthy();
  });

  it("forwards ref", () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<Progress ref={ref} value={50} />);
    expect(ref.current).toBeTruthy();
  });
});

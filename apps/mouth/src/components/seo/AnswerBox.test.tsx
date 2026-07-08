import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KeyTakeaway } from "./AnswerBox";

describe("KeyTakeaway", () => {
  it("renders explicit points", () => {
    render(<KeyTakeaway points={["First point", "Second point"]} />);

    expect(screen.getByText("First point")).toBeTruthy();
    expect(screen.getByText("Second point")).toBeTruthy();
  });

  it("renders MDX children when points are omitted", () => {
    render(
      <KeyTakeaway>
        <strong>TL;DR:</strong> MDX-authored takeaway text.
      </KeyTakeaway>,
    );

    expect(screen.getByText("TL;DR:")).toBeTruthy();
    expect(screen.getByText(/MDX-authored takeaway text/)).toBeTruthy();
  });
});

import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Label } from "./label";

describe("Label", () => {
  it("renders as a label element", () => {
    render(<Label>Email</Label>);
    const el = screen.getByText("Email");
    expect(el.tagName).toBe("LABEL");
  });

  it("applies base styling classes", () => {
    render(<Label data-testid="label">Name</Label>);
    const el = screen.getByTestId("label");
    expect(el.className).toContain("text-sm");
    expect(el.className).toContain("font-medium");
  });

  it("merges custom className", () => {
    render(
      <Label className="my-label" data-testid="label">
        Field
      </Label>,
    );
    expect(screen.getByTestId("label").className).toContain("my-label");
  });

  it("forwards ref", () => {
    const ref = React.createRef<HTMLLabelElement>();
    render(<Label ref={ref}>Ref test</Label>);
    expect(ref.current).toBeInstanceOf(HTMLLabelElement);
  });

  it("connects to input via htmlFor attribute", () => {
    render(
      <>
        <Label htmlFor="email-input">Email</Label>
        <input id="email-input" type="email" />
      </>,
    );
    const label = screen.getByText("Email");
    expect(label).toHaveAttribute("for", "email-input");
  });
});

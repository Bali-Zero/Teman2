import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Textarea } from "./textarea";

describe("Textarea", () => {
  it("renders a textarea element", () => {
    render(<Textarea data-testid="ta" />);
    const el = screen.getByTestId("ta");
    expect(el.tagName).toBe("TEXTAREA");
  });

  it("applies base styling classes", () => {
    render(<Textarea data-testid="ta" />);
    const el = screen.getByTestId("ta");
    expect(el.className).toContain("rounded-md");
    expect(el.className).toContain("border");
    expect(el.className).toContain("min-h-[80px]");
  });

  it("merges custom className", () => {
    render(<Textarea data-testid="ta" className="custom-class" />);
    expect(screen.getByTestId("ta").className).toContain("custom-class");
  });

  it("forwards ref", () => {
    const ref = React.createRef<HTMLTextAreaElement>();
    render(<Textarea ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement);
  });

  it("handles onChange events", () => {
    const onChange = vi.fn();
    render(<Textarea data-testid="ta" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("ta"), {
      target: { value: "Hello" },
    });
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("supports placeholder text", () => {
    render(<Textarea placeholder="Type here..." />);
    expect(screen.getByPlaceholderText("Type here...")).toBeInTheDocument();
  });

  it("supports disabled state", () => {
    render(<Textarea data-testid="ta" disabled />);
    expect(screen.getByTestId("ta")).toBeDisabled();
  });
});

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AutoResizeTextarea } from "./auto-resize-textarea";

describe("AutoResizeTextarea", () => {
  it("renders a textarea with the given value", () => {
    render(<AutoResizeTextarea value="Hello world" readOnly data-testid="ta" />);
    const ta = screen.getByTestId("ta") as HTMLTextAreaElement;
    expect(ta.tagName).toBe("TEXTAREA");
    expect(ta.value).toBe("Hello world");
  });

  it("applies overflow-hidden and resize-none classes", () => {
    render(<AutoResizeTextarea value="" readOnly data-testid="ta" />);
    const ta = screen.getByTestId("ta");
    expect(ta.className).toContain("overflow-hidden");
    expect(ta.className).toContain("resize-none");
  });

  it("merges custom className", () => {
    render(
      <AutoResizeTextarea value="" readOnly className="my-class" data-testid="ta" />,
    );
    expect(screen.getByTestId("ta").className).toContain("my-class");
  });

  it("fires onChange when typing", () => {
    const onChange = vi.fn();
    render(
      <AutoResizeTextarea
        value=""
        onChange={onChange}
        data-testid="ta"
      />,
    );
    fireEvent.change(screen.getByTestId("ta"), {
      target: { value: "new text" },
    });
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("supports placeholder", () => {
    render(
      <AutoResizeTextarea value="" readOnly placeholder="Type here..." />,
    );
    expect(screen.getByPlaceholderText("Type here...")).toBeInTheDocument();
  });
});

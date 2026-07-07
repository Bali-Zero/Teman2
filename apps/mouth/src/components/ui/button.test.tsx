import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./button";

describe("Button", () => {
  it("renders an accessible button with a safe default type", () => {
    render(<Button>Save changes</Button>);

    const button = screen.getByRole("button", { name: "Save changes" });
    expect(button).toBeVisible();
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveClass("bg-[var(--accent)]", "h-9");
  });

  it("preserves native button props and disabled behavior", () => {
    const handleClick = vi.fn();

    render(
      <Button
        aria-label="Delete case"
        disabled
        onClick={handleClick}
        type="submit"
      />,
    );

    const button = screen.getByRole("button", { name: "Delete case" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("type", "submit");

    fireEvent.click(button);

    expect(handleClick).not.toHaveBeenCalled();
  });

  it("merges variant, size, and custom classes", () => {
    render(
      <Button variant="outline" size="sm" className="tracking-wide">
        Review
      </Button>,
    );

    expect(screen.getByRole("button", { name: "Review" })).toHaveClass(
      "border",
      "h-8",
      "tracking-wide",
    );
  });

  it("renders slotted children without forcing button-only attributes", () => {
    render(
      <Button asChild>
        <a href="/kbli">Open KBLI</a>
      </Button>,
    );

    const link = screen.getByRole("link", { name: "Open KBLI" });
    expect(link).toHaveAttribute("href", "/kbli");
    expect(link).not.toHaveAttribute("type");
    expect(link).toHaveClass("inline-flex", "bg-[var(--accent)]");
  });
});

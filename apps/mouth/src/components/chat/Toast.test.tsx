import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Toast } from "./Toast";

describe("Toast", () => {
  it("renders the toast message and has correct layout structure", () => {
    render(<Toast message="Hello, World!" type="success" onClose={() => {}} />);
    expect(screen.getByText("Hello, World!")).toBeInTheDocument();
  });

  it("applies the correct background color class for success type", () => {
    const { container } = render(
      <Toast message="Success" type="success" onClose={() => {}} />
    );
    expect(container.firstChild).toHaveClass("bg-green-600");
  });

  it("applies the correct background color class for error type", () => {
    const { container } = render(
      <Toast message="Error" type="error" onClose={() => {}} />
    );
    expect(container.firstChild).toHaveClass("bg-red-600");
  });

  it("has accessible attributes and styles on the close button", () => {
    render(<Toast message="Test" type="success" onClose={() => {}} />);
    const closeButton = screen.getByRole("button", { name: /close/i });

    expect(closeButton).toBeInTheDocument();
    expect(closeButton).toHaveAttribute("type", "button");
    expect(closeButton).toHaveAttribute("title", "Close");
    expect(closeButton).toHaveClass("focus-ring", "rounded");
  });

  it("calls onClose callback when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<Toast message="Test" type="success" onClose={onClose} />);
    const closeButton = screen.getByRole("button", { name: /close/i });

    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Toast } from "./Toast";

describe("Toast Component", () => {
  const defaultProps = {
    message: "Success message",
    type: "success" as const,
    onClose: vi.fn(),
  };

  it("renders success toast with correct message and styling", () => {
    render(<Toast {...defaultProps} />);

    // Verify message is rendered
    expect(screen.getByText("Success message")).toBeDefined();

    // Verify container styling for success
    const container = screen.getByRole("status");
    expect(container).toBeDefined();
    expect(container.className).toContain("bg-green-600");
  });

  it("renders error toast with correct background styling", () => {
    render(<Toast {...defaultProps} message="Error message" type="error" />);

    // Verify message is rendered
    expect(screen.getByText("Error message")).toBeDefined();

    // Verify container styling for error
    const container = screen.getByRole("status");
    expect(container).toBeDefined();
    expect(container.className).toContain("bg-red-600");
  });

  it("includes correct accessibility attributes on the close button", () => {
    render(<Toast {...defaultProps} />);

    const closeButton = screen.getByRole("button", { name: "Close" });
    expect(closeButton).toBeDefined();
    expect(closeButton.getAttribute("type")).toBe("button");
    expect(closeButton.getAttribute("title")).toBe("Close");
    expect(closeButton.className).toContain("focus-ring");
  });

  it("triggers onClose callback when close button is clicked", () => {
    const onCloseMock = vi.fn();
    render(<Toast {...defaultProps} onClose={onCloseMock} />);

    const closeButton = screen.getByRole("button", { name: "Close" });
    fireEvent.click(closeButton);

    expect(onCloseMock).toHaveBeenCalledTimes(1);
  });
});

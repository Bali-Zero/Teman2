import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StateBadge } from "./StateBadge";
import { ProcessStepState } from "@/lib/schemas/process";

describe("StateBadge", () => {
  it("renders default label for each state", () => {
    for (const state of ProcessStepState.options) {
      const { unmount } = render(<StateBadge state={state} />);
      // Every badge must carry an aria-label starting with "Status: ".
      expect(screen.getByLabelText(/^Status:/i)).toBeInTheDocument();
      unmount();
    }
  });

  it("sets aria-label for screen readers", () => {
    render(<StateBadge state="completed" />);
    const el = screen.getByLabelText(/Status: Completed/i);
    expect(el).toBeInTheDocument();
  });

  it("applies state style via inline CSS", () => {
    const { container } = render(<StateBadge state="cancelled" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.color).toBeTruthy();
    expect(el.style.backgroundColor).toBeTruthy();
    expect(el.style.borderColor).toBeTruthy();
  });

  it("uses override label when provided", () => {
    render(<StateBadge state="on_process" label="Custom Label" />);
    expect(screen.getByText("Custom Label")).toBeInTheDocument();
  });

  it("supports both canonical and legacy states", () => {
    const { rerender } = render(<StateBadge state="inquiry" />);
    expect(screen.getByText(/Inquiry/i)).toBeInTheDocument();
    rerender(<StateBadge state="in_progress" />);
    expect(screen.getByText(/In Progress/i)).toBeInTheDocument();
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TimelineStep } from "./TimelineStep";
import type { ProcessStep } from "@/lib/schemas/process";

function makeStep(overrides: Partial<ProcessStep> = {}): ProcessStep {
  return {
    status: "on_process",
    label: "On Process",
    completed: false,
    is_current: false,
    changed_at: null,
    changed_by: null,
    ...overrides,
  };
}

describe("TimelineStep", () => {
  it("renders the BE-provided step label as heading", () => {
    render(
      <TimelineStep
        step={makeStep({
          label: "Waiting for Documents",
          status: "waiting_documents",
        })}
        onSelect={() => {}}
        isLast={false}
      />,
    );
    // Heading carries the label
    const heading = screen.getByRole("heading", { level: 3 });
    expect(heading).toHaveTextContent("Waiting for Documents");
  });

  it("shows 'current' marker when is_current=true, hides it otherwise", () => {
    const { rerender } = render(
      <TimelineStep
        step={makeStep({ is_current: true })}
        onSelect={() => {}}
        isLast={false}
      />,
    );
    expect(screen.getByText(/current/i)).toBeInTheDocument();

    rerender(
      <TimelineStep
        step={makeStep({ is_current: false })}
        onSelect={() => {}}
        isLast={false}
      />,
    );
    expect(screen.queryByText(/^current$/i)).not.toBeInTheDocument();
  });

  it("formats changed_at into a date line; hides line when null", () => {
    const { rerender, container } = render(
      <TimelineStep
        step={makeStep({
          changed_at: "2026-04-18T10:15:00Z",
          changed_by: "asya",
        })}
        onSelect={() => {}}
        isLast={false}
      />,
    );
    // A date paragraph is rendered with year present (locale-insensitive check)
    const p = container.querySelector("p");
    expect(p).not.toBeNull();
    expect(p!.textContent || "").toMatch(/2026/);
    // changed_by appended with separator
    expect(p!.textContent || "").toMatch(/asya/);

    rerender(
      <TimelineStep
        step={makeStep({ changed_at: null, changed_by: null })}
        onSelect={() => {}}
        isLast={false}
      />,
    );
    // No date paragraph
    expect(container.querySelector("p")).toBeNull();
  });

  it("fires onSelect when the button is clicked", () => {
    const onSelect = vi.fn();
    const step = makeStep({ label: "Inquiry", status: "inquiry" });
    render(<TimelineStep step={step} onSelect={onSelect} isLast />);
    fireEvent.click(screen.getByRole("button"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(step);
  });

  it("fires onSelect on Enter and Space key", () => {
    const onSelect = vi.fn();
    const step = makeStep();
    render(<TimelineStep step={step} onSelect={onSelect} isLast />);
    const button = screen.getByRole("button");
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyDown(button, { key: " " });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("reflects completed state via data attribute on the dot", () => {
    const { rerender } = render(
      <TimelineStep
        step={makeStep({ completed: true })}
        onSelect={() => {}}
        isLast
      />,
    );
    expect(screen.getByTestId("timeline-step-dot")).toHaveAttribute(
      "data-completed",
      "true",
    );

    rerender(
      <TimelineStep
        step={makeStep({ completed: false })}
        onSelect={() => {}}
        isLast
      />,
    );
    expect(screen.getByTestId("timeline-step-dot")).toHaveAttribute(
      "data-completed",
      "false",
    );
  });
});

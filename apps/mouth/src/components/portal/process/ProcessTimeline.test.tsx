import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProcessTimeline } from "./ProcessTimeline";
import type { ProcessStep } from "@/lib/schemas/process";

function makeStep(overrides: Partial<ProcessStep> = {}): ProcessStep {
  return {
    status: "inquiry",
    label: "Inquiry",
    completed: false,
    is_current: false,
    changed_at: null,
    changed_by: null,
    ...overrides,
  };
}

describe("ProcessTimeline", () => {
  it("renders empty-state message when steps is empty", () => {
    render(<ProcessTimeline steps={[]} onSelect={() => {}} />);
    expect(screen.getByText(/no steps yet/i)).toBeInTheDocument();
    // No <ol> should be rendered
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders an <ol> with aria-label and one <li> per step", () => {
    const steps: ProcessStep[] = [
      makeStep({ status: "inquiry", label: "Inquiry" }),
      makeStep({ status: "waiting_documents", label: "Waiting for Documents" }),
      makeStep({ status: "on_process", label: "On Process", is_current: true }),
    ];
    render(<ProcessTimeline steps={steps} onSelect={() => {}} />);
    const list = screen.getByRole("list", { name: /practice timeline/i });
    expect(list.tagName.toLowerCase()).toBe("ol");
    expect(list.getAttribute("aria-label")).toBe("Practice timeline");
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
  });

  it("propagates onSelect to child steps", () => {
    const onSelect = vi.fn();
    const steps: ProcessStep[] = [
      makeStep({ status: "inquiry", label: "Inquiry" }),
      makeStep({ status: "on_process", label: "On Process" }),
    ];
    render(<ProcessTimeline steps={steps} onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[1]);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(steps[1]);
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepDetailDrawer } from "./StepDetailDrawer";
import type { ProcessStep } from "@/lib/schemas/process";

const step: ProcessStep = {
  status: "on_process",
  label: "On Process",
  completed: false,
  is_current: true,
  changed_at: "2026-04-01T10:30:00Z",
  changed_by: "alice",
};

describe("StepDetailDrawer", () => {
  it("renders step label in dialog title when open", () => {
    render(<StepDetailDrawer step={step} open onClose={() => {}} />);
    // Radix mounts Portal in document.body — query with screen
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // Title text
    expect(screen.getAllByText(/On Process/i).length).toBeGreaterThan(0);
  });

  it("renders current step flag Yes", () => {
    render(<StepDetailDrawer step={step} open onClose={() => {}} />);
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("calls onClose on ESC", async () => {
    const onClose = vi.fn();
    render(<StepDetailDrawer step={step} open onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose on Close button click", async () => {
    const onClose = vi.fn();
    render(<StepDetailDrawer step={step} open onClose={onClose} />);
    await userEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalled();
  });

  it("handles null step without crashing", () => {
    const { container } = render(
      <StepDetailDrawer step={null} open onClose={() => {}} />,
    );
    // Title should be the em-dash placeholder
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(container).toBeInTheDocument();
  });

  it("handles missing changed_by gracefully", () => {
    const noAuthor: ProcessStep = { ...step, changed_by: null };
    render(<StepDetailDrawer step={noAuthor} open onClose={() => {}} />);
    expect(screen.queryByText("Changed by")).not.toBeInTheDocument();
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProcessStepper } from "./ProcessStepper";
import type { ProcessTimelineStep } from "@/lib/api/portal/portal.types";

function makeStep(
  overrides: Partial<ProcessTimelineStep> = {},
): ProcessTimelineStep {
  return {
    status: "on_process",
    label: "On Process",
    completed: false,
    is_current: false,
    changed_at: null,
    ...overrides,
  };
}

describe("ProcessStepper", () => {
  it("renders nothing for an empty step list", () => {
    const { container } = render(<ProcessStepper steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the step label and formatted date", () => {
    render(
      <ProcessStepper
        steps={[
          makeStep({
            label: "Waiting for Documents",
            changed_at: "2026-04-18T10:15:00Z",
          }),
        ]}
      />,
    );
    expect(screen.getByText("Waiting for Documents")).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("never renders a staff actor identity next to the date, even if a stale payload still carries changed_by", () => {
    // ProcessTimelineStep no longer declares `changed_by` — this simulates
    // a stale cached/legacy response that still includes it, to prove the
    // stepper ignores it rather than merely lacking a type for it. The
    // original leak rendered only the local-part (`changed_by.split("@")[0]`),
    // so the marker below must be distinctive enough that the local-part
    // alone (no "@") would still be caught.
    const staleStep = {
      ...makeStep({ changed_at: "2026-04-18T10:15:00Z" }),
      changed_by: "leaked-actor-marker@example.com",
    } as ProcessTimelineStep;
    const { container } = render(<ProcessStepper steps={[staleStep]} />);
    expect(container.textContent || "").not.toMatch(/leaked-actor-marker/);
  });
});

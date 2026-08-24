import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import { SavePlanBar } from "./SavePlanBar";

const originalPrintDescriptor = Object.getOwnPropertyDescriptor(
  window,
  "print",
);

describe("SavePlanBar print action", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    if (originalPrintDescriptor) {
      Object.defineProperty(window, "print", originalPrintDescriptor);
    }
  });

  it("is keyboard-accessible by its visible name and calls window.print without a network request", () => {
    const print = vi.fn();
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    Object.defineProperty(window, "print", {
      configurable: true,
      value: print,
    });

    render(<SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />);

    const printButton = screen.getByRole("button", {
      name: "Print / Save as PDF",
    });
    expect(printButton).toHaveAttribute("type", "button");

    printButton.focus();
    expect(printButton).toHaveFocus();
    fireEvent.click(printButton);

    expect(print).toHaveBeenCalledOnce();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("is a safe no-op when the browser print API is unavailable", () => {
    Object.defineProperty(window, "print", {
      configurable: true,
      value: undefined,
    });

    render(<SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />);

    expect(() =>
      fireEvent.click(
        screen.getByRole("button", { name: "Print / Save as PDF" }),
      ),
    ).not.toThrow();
  });

  it("ships targeted print rules without hiding content buttons globally", () => {
    const { container } = render(
      <SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />,
    );
    const css = container.querySelector("style")?.textContent ?? "";

    // jsdom cannot paginate or emulate a print preview. These assertions
    // intentionally verify only that the browser-facing rules are emitted.
    expect(css).toContain("@media print");
    expect(css).toContain("--surface-base: #ffffff");
    expect(css).toContain(".bz-shs-save-plan-bar,");
    expect(css).toContain(".bz-shs-option,");
    expect(css).toContain(".bz-shs-scenario-toggle-trigger,");
    expect(css).not.toMatch(/(?:^|[,{])\s*button\s*(?=[,{])/);
    expect(css).toContain("break-inside: avoid");
    expect(css).toContain('input[type="checkbox"]');
    expect(css).toContain('a[href^="https://wa.me"]::after');
    expect(css).toContain('content: " (" attr(href) ")"');
  });
});

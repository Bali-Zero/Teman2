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

// P0 2026-08-24: the "Clear saved plan" button used to fire onClear on a
// single activation, with no undo — on a touch device (no :hover) that
// meant the plan could vanish on the very first tap. These pin the
// two-step arm/confirm behaviour, not the pixels (jsdom resolves neither
// clamp() nor :hover).
describe("SavePlanBar clear-plan two-step confirm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not clear on a single activation", () => {
    const onClear = vi.fn();
    render(<SavePlanBar plan={emptyPlan()} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));

    expect(onClear).not.toHaveBeenCalled();
  });

  it("clears on a second activation", () => {
    const onClear = vi.fn();
    render(<SavePlanBar plan={emptyPlan()} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Press again to clear your plan" }),
    );

    expect(onClear).toHaveBeenCalledOnce();
  });

  it("disarms on Escape — a subsequent single activation does not clear", () => {
    const onClear = vi.fn();
    render(<SavePlanBar plan={emptyPlan()} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));
    fireEvent.keyDown(
      screen.getByRole("button", { name: "Press again to clear your plan" }),
      { key: "Escape" },
    );

    // Disarmed: the label reverted, so this click only re-arms it.
    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));

    expect(onClear).not.toHaveBeenCalled();
  });

  it("announces the armed state through the existing live region", () => {
    render(<SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />);

    expect(screen.getByRole("status")).not.toHaveTextContent(/ready to clear/i);

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Ready to clear — press again to confirm, or Escape to cancel.",
    );
  });

  it("keeps the resting clear button neutral — no accent/danger token (regression guard, #4795)", () => {
    const { container } = render(
      <SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />,
    );
    const css = Array.from(container.querySelectorAll("style"))
      .map((style) => style.textContent ?? "")
      .join("\n");
    const restingRule = css.match(/\.bz-shs-clear-plan\s*\{([^}]*)\}/)?.[1];

    expect(restingRule).toContain("border: 1px solid var(--text-secondary)");
    expect(restingRule).toContain("color: var(--text-secondary)");
    expect(restingRule).not.toContain("--accent-funnel");
    expect(restingRule).not.toContain("--color-error");
    // The armed rule itself is scoped to the compound `.bz-shs-clear-armed`
    // class and never applies at rest.
    expect(css).toMatch(
      /\.bz-shs-clear-plan\.bz-shs-clear-armed\s*\{[^}]*border-color:\s*var\(--accent-funnel\)[^}]*color:\s*var\(--bz-shs-clear-armed-active\)/s,
    );
  });
});

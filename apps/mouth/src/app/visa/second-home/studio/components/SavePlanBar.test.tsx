import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import { SavePlanBar } from "./SavePlanBar";

const originalPrintDescriptor = Object.getOwnPropertyDescriptor(
  window,
  "print",
);

describe("SavePlanBar resting-state boundary (WCAG 2.2 SC 1.4.11)", () => {
  // Regression guard (2026-09-01): Save/Copy-Link/Print share `buttonStyle`,
  // whose border is their ONLY resting-state boundary (transparent fill).
  // --color-border-subtle composites to 1.21:1 on carta / 1.31:1 on white —
  // decorative-only per merahPutihDayVars.ts's own comment, and below the
  // 3:1 non-text UI floor (WCAG 1.4.11). --border-strong (#7a8093) measures
  // 3.64:1 on carta / 3.94:1 on white — the same token StudioApp.tsx's
  // navButtonStyle already uses for its Back button boundary. The "Clear
  // saved plan" button is deliberately excluded: it owns a separate
  // treatment via CLEAR_BUTTON_STYLES, pinned by its own tests below.
  it("gives Save, Copy-Link and Print an AA-clearing resting border, never the decorative hairline", () => {
    render(<SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />);

    for (const name of [
      "Save on this device",
      "Copy plan link",
      "Print / Save as PDF",
    ]) {
      const button = screen.getByRole("button", { name });
      const inlineStyle = button.getAttribute("style") ?? "";
      expect(inlineStyle).toContain("border: 1px solid var(--border-strong)");
      expect(inlineStyle).not.toContain("--color-border-subtle");
    }
  });
});

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
    // 2026-08-24: the verdict page's "Back to your answers" nav control is
    // dead weight in a printed/saved PDF — hidden alongside the other
    // controls this block already suppresses.
    expect(css).toContain(".bz-shs-back-to-answers");
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
    vi.useRealTimers();
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
  });

  // Regression guard (#4826, revised round c; re-pinned on the Merah Putih
  // day palette 2026-08-31): round b pinned the armed state to
  // --state-warning (amber) to escape a red collision with the price panel
  // — but --state-warning is ALSO VerdictPanel's `edge_case` band accent
  // (same outline + light-tint structure), so that just moved the same
  // defect onto a different hue. The fix changes the CHANNEL: a solid,
  // opaque fill instead of a thin outline over a light tint — no verdict
  // band and no price panel ever paints one, so the fill reads as "another
  // kind of control" regardless of hue.
  //
  // What this test used to pin was the MEANS, not the property: the literal
  // color-mix(--accent-funnel 85%, black). That mix existed only to rescue
  // #ff3344's 3.62:1 under white on the retired navy scheme, and it minted
  // a fourth red (~#aa0e27) belonging to no token. The property it was
  // standing in for is what is pinned now: the fill is a DECLARED token, in
  // the one hue family this page leaves free (VerdictPanel keeps
  // not_eligible deliberately neutral rather than --state-danger), never
  // the funnel red that would collide with the price panel, never
  // --state-warning, and never a red derived by mixing one of those toward
  // black. The boundary stays a DIFFERENT token from the fill
  // (--text-on-accent) — redundant on a light ground but harmless, and
  // still what a dark-ground rendering would need.
  it("arms the clear button with a solid fill and a separate high-contrast boundary, never a bare accent outline or the warning accent (regression guard, #4826)", () => {
    const { container } = render(
      <SavePlanBar plan={emptyPlan()} onClear={vi.fn()} />,
    );
    const css = Array.from(container.querySelectorAll("style"))
      .map((style) => style.textContent ?? "")
      .join("\n");
    const armedRule = css.match(
      /\.bz-shs-clear-plan\.bz-shs-clear-armed\s*\{([^}]*)\}/,
    )?.[1];

    // Solid, opaque fill — not a light color-mix tint like every verdict
    // band and the price panel use.
    expect(armedRule).toContain("background: var(--bz-shs-clear-armed-fill)");
    expect(armedRule).toMatch(
      /--bz-shs-clear-armed-fill:\s*var\(--color-error[^)]*\)/,
    );
    // The fill is a declared token, never a red derived by mixing another
    // one toward black — that is how a fourth, undeclared red gets minted.
    expect(armedRule).not.toContain("color-mix");
    // Never the funnel red: that is the price panel's own border colour.
    expect(armedRule).not.toContain("--accent-funnel");
    // Boundary is --text-on-accent, NOT the (low-contrast-vs-surface) fill
    // token — this is what keeps the 3:1 UI-boundary floor met without
    // breaking the 4.5:1 text-vs-fill floor.
    expect(armedRule).toContain("border-color: var(--text-on-accent, #fff)");
    const focusRule = css.match(
      /\.bz-shs-clear-plan\.bz-shs-clear-armed:focus-visible\s*\{([^}]*)\}/,
    )?.[1];
    expect(focusRule).toContain(
      "outline: 3px solid var(--text-on-accent, #fff)",
    );
    // Never regress to round b's warning-amber collision with edge_case.
    expect(armedRule).not.toContain("--state-warning");
  });

  it("disarms on blur — a subsequent single activation does not clear", () => {
    const onClear = vi.fn();
    render(<SavePlanBar plan={emptyPlan()} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));
    fireEvent.blur(
      screen.getByRole("button", { name: "Press again to clear your plan" }),
    );

    // Disarmed: the label reverted, so this click only re-arms it.
    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));

    expect(onClear).not.toHaveBeenCalled();
  });

  it("disarms after the 5s arm timeout — a subsequent single activation does not clear", () => {
    vi.useFakeTimers();
    const onClear = vi.fn();
    render(<SavePlanBar plan={emptyPlan()} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Disarmed: the label reverted, so this click only re-arms it.
    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));

    expect(onClear).not.toHaveBeenCalled();
  });

  // Not a console.error/"state update on an unmounted component" assertion:
  // proven empirically vacuous first (mutation-tested — see PR discussion).
  // React 18+ no longer warns on a hook-based setState after unmount, so
  // that signal would pass identically whether or not the cleanup exists.
  // This asserts the actual mechanism instead: the useEffect cleanup must
  // call clearTimeout on the pending arm timer when the component unmounts.
  it("clears the pending arm timer on unmount", () => {
    const onClear = vi.fn();
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    const { unmount } = render(
      <SavePlanBar plan={emptyPlan()} onClear={onClear} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Clear saved plan" }));
    const callsBeforeUnmount = clearTimeoutSpy.mock.calls.length;
    unmount();

    expect(clearTimeoutSpy.mock.calls.length).toBeGreaterThan(
      callsBeforeUnmount,
    );
  });
});

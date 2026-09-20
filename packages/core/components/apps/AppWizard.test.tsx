import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { AppWizard } from "./AppWizard";
import type { WizardStep } from "./AppWizard";

function makeSteps(): WizardStep[] {
  return [
    {
      id: "a",
      title: "A",
      summary: (v) => `A: ${v ?? "?"}`,
      render: ({ value, setValue }) => (
        <button data-testid="a-btn" onClick={() => setValue("a-value")}>
          pick-a ({String(value ?? "empty")})
        </button>
      ),
      validate: (v) => (v ? null : "pick A"),
    },
    {
      id: "b",
      title: "B",
      summary: (v) => `B: ${v ?? "?"}`,
      render: ({ value, setValue }) => (
        <button data-testid="b-btn" onClick={() => setValue("b-value")}>
          pick-b ({String(value ?? "empty")})
        </button>
      ),
      validate: (v) => (v ? null : "pick B"),
    },
  ];
}

describe("AppWizard", () => {
  beforeEach(() => {
    vi.stubGlobal("navigator", { vibrate: vi.fn(() => true) });
    window.matchMedia = vi.fn().mockImplementation((q: string) => ({
      matches: false,
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders the first step's body on mount", () => {
    const { getByTestId } = render(
      <AppWizard steps={makeSteps()} onComplete={vi.fn()} />,
    );
    expect(getByTestId("a-btn")).toBeTruthy();
  });

  it("renders next-step peek under current", () => {
    const { getByText } = render(
      <AppWizard steps={makeSteps()} onComplete={vi.fn()} />,
    );
    // next step peek "— B ↓"
    expect(getByText(/B\s*↓/)).toBeTruthy();
  });

  it("advances to next step and shows previous summary stacked above", () => {
    const { getByTestId, getByText } = render(
      <AppWizard steps={makeSteps()} onComplete={vi.fn()} />,
    );
    fireEvent.click(getByTestId("a-btn")); // setValue
    fireEvent.click(getByText(/^Next$/));
    expect(getByTestId("b-btn")).toBeTruthy();
    expect(getByText(/A: a-value/)).toBeTruthy();
  });

  it("haptic fires on Next success", () => {
    const { getByTestId, getByText } = render(
      <AppWizard steps={makeSteps()} onComplete={vi.fn()} />,
    );
    fireEvent.click(getByTestId("a-btn"));
    fireEvent.click(getByText(/^Next$/));
    expect(navigator.vibrate).toHaveBeenCalledWith(6);
  });

  it("blocks Next with validation error and jiggles", () => {
    const { getByText, getByRole } = render(
      <AppWizard steps={makeSteps()} onComplete={vi.fn()} />,
    );
    fireEvent.click(getByText(/^Next$/));
    expect(getByRole("alert").textContent).toContain("pick A");
  });

  it("calls onComplete on final Next after all validations pass", () => {
    const onComplete = vi.fn();
    const { getByTestId, getByText } = render(
      <AppWizard steps={makeSteps()} onComplete={onComplete} />,
    );
    fireEvent.click(getByTestId("a-btn"));
    fireEvent.click(getByText(/^Next$/));
    fireEvent.click(getByTestId("b-btn"));
    fireEvent.click(getByText(/See result/));
    expect(onComplete).toHaveBeenCalledWith({
      a: "a-value",
      b: "b-value",
    });
    expect(navigator.vibrate).toHaveBeenCalledWith([20, 30, 20]);
  });
});

/**
 * The chrome is the only English left in a funnel that speaks another
 * language, so it takes labels — and a caller that passes none must keep the
 * words it renders today, which is what the first test below pins.
 */
describe("AppWizard — chrome labels", () => {
  it("defaults to English when no labels are passed", () => {
    const { getByText } = render(
      <AppWizard steps={makeSteps()} onComplete={vi.fn()} />,
    );
    expect(getByText("Step 1 of 2")).toBeTruthy();
    expect(getByText("Next")).toBeTruthy();
  });

  it("renders the labels it is given, including the last-step word", () => {
    const { getByText, getByTestId } = render(
      <AppWizard
        steps={makeSteps()}
        onComplete={vi.fn()}
        labels={{
          stepOf: (current, total) => `Langkah ${current} dari ${total}`,
          back: "Kembali",
          next: "Lanjut",
          finish: "Lihat hasil",
        }}
      />,
    );
    expect(getByText("Langkah 1 dari 2")).toBeTruthy();
    fireEvent.click(getByTestId("a-btn"));
    fireEvent.click(getByText("Lanjut"));
    expect(getByText("Langkah 2 dari 2")).toBeTruthy();
    expect(getByText("Kembali")).toBeTruthy();
    expect(getByText("Lihat hasil")).toBeTruthy();
  });

  it("falls back per-field: a partial override keeps the English rest", () => {
    const { getByText } = render(
      <AppWizard
        steps={makeSteps()}
        onComplete={vi.fn()}
        labels={{ next: "Lanjut" }}
      />,
    );
    expect(getByText("Step 1 of 2")).toBeTruthy();
    expect(getByText("Lanjut")).toBeTruthy();
  });
});

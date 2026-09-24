import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WizardStep } from "@balizero/core";
import { VoaWizard } from "./VoaWizard";

const pick = (id: string, options: string[]): WizardStep => ({
  id,
  title: id === "a" ? "First" : "Second",
  summary: (v) => String(v ?? "?"),
  render: ({ value, setValue }) => (
    <div>
      {options.map((o) => (
        <button
          key={o}
          type="button"
          aria-pressed={value === o}
          onClick={() => setValue(o)}
        >
          {o}
        </button>
      ))}
    </div>
  ),
  validate: (v) => (v ? null : "Pick one"),
});

const LABELS = {
  stepOf: (c: number, t: number) => `Step ${c} of ${t}`,
  progress: "Your progress",
  back: "Back",
  next: "Next",
  finish: "See result",
  change: "Change",
  assure: "No payment on this page.",
};

function renderWizard(onComplete = vi.fn()) {
  render(
    <VoaWizard
      steps={[pick("a", ["Alpha", "Beta"]), pick("b", ["Gamma"])]}
      labels={LABELS}
      onComplete={onComplete}
    />,
  );
  return onComplete;
}

describe("VoaWizard", () => {
  beforeEach(() => window.localStorage.clear());

  it("labels every step in the rail and marks the current one", () => {
    renderWizard();
    const rail = screen.getByRole("list", { name: "Your progress" });
    expect(rail).toHaveTextContent("First");
    expect(rail).toHaveTextContent("Second");
    expect(rail.querySelector('[aria-current="step"]')).toHaveTextContent(
      "First",
    );
    expect(screen.getByText("Step 1 of 2")).toBeInTheDocument();
  });

  it("reads 'not yet' before an answer and still explains itself on press", () => {
    renderWizard();
    const next = screen.getByRole("button", { name: "Next" });
    expect(next).toHaveAttribute("data-ready", "false");
    expect(next).not.toBeDisabled();
    fireEvent.click(next);
    expect(screen.getByRole("alert")).toHaveTextContent("Pick one");
    fireEvent.click(screen.getByRole("button", { name: "Beta" }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(next).toHaveAttribute("data-ready", "true");
  });

  it("files a given answer above the next question, and Change goes back to it", () => {
    renderWizard();
    fireEvent.click(screen.getByRole("button", { name: "Beta" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const filed = screen.getByRole("term");
    expect(filed).toHaveTextContent("First");
    expect(screen.getByRole("definition")).toHaveTextContent("Beta");
    // No ghost peek of the next step's title survives outside the rail.
    expect(screen.queryByText(/↓/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Change: First" }));
    expect(screen.getByRole("button", { name: "Beta" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("completes with every answer on the last step", () => {
    const onComplete = renderWizard();
    fireEvent.click(screen.getByRole("button", { name: "Alpha" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Gamma" }));
    fireEvent.click(screen.getByRole("button", { name: "See result" }));
    expect(onComplete).toHaveBeenCalledWith({ a: "Alpha", b: "Gamma" });
  });

  it("moves focus to the new step's own heading, never a nameless wrapper", () => {
    renderWizard();
    fireEvent.click(screen.getByRole("button", { name: "Beta" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const heading = screen.getByRole("heading", { name: "Second", level: 2 });
    expect(heading).toHaveFocus();
  });

  it("never moves focus on first paint", () => {
    renderWizard();
    const heading = screen.getByRole("heading", { name: "First", level: 2 });
    expect(heading).not.toHaveFocus();
  });
});

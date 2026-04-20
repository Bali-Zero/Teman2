import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { AppHeroForm } from "./AppHeroForm";

describe("AppHeroForm", () => {
  it("renders headline and submit label", () => {
    const { getByText } = render(
      <AppHeroForm headline="H" submitLabel="GO" onSubmit={vi.fn()}>
        <input data-testid="f" />
      </AppHeroForm>,
    );
    expect(getByText("H")).toBeTruthy();
    expect(getByText("GO")).toBeTruthy();
  });

  it("calls onSubmit when form is submitted", () => {
    const onSubmit = vi.fn((e) => e.preventDefault());
    const { getByText } = render(
      <AppHeroForm headline="H" submitLabel="GO" onSubmit={onSubmit}>
        <input />
      </AppHeroForm>,
    );
    fireEvent.click(getByText("GO"));
    expect(onSubmit).toHaveBeenCalled();
  });

  it("disables submit when pending=true and shows 'Working…' label", () => {
    const { getByText } = render(
      <AppHeroForm headline="H" submitLabel="GO" onSubmit={vi.fn()} pending>
        <input />
      </AppHeroForm>,
    );
    const btn = getByText("Working…") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("renders error alert when error prop provided", () => {
    const { getByRole } = render(
      <AppHeroForm headline="H" submitLabel="GO" onSubmit={vi.fn()} error="Bad input">
        <input />
      </AppHeroForm>,
    );
    expect(getByRole("alert").textContent).toContain("Bad input");
  });

  it("renders sentence variant when sentenceTemplate + sentenceFields provided", () => {
    const { getByText, getByTestId } = render(
      <AppHeroForm
        headline="H"
        submitLabel="GO"
        onSubmit={vi.fn()}
        sentenceTemplate="I entered on {entry} with a {visa} visa."
        sentenceFields={{
          entry: <input data-testid="f-entry" />,
          visa: <select data-testid="f-visa"><option>E33G</option></select>,
        }}
      />,
    );
    expect(getByText(/I entered on/)).toBeTruthy();
    expect(getByTestId("f-entry")).toBeTruthy();
    expect(getByTestId("f-visa")).toBeTruthy();
  });
});

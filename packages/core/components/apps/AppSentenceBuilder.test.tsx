import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AppSentenceBuilder } from "./AppSentenceBuilder";

describe("AppSentenceBuilder", () => {
  it("renders the template with field slots interpolated", () => {
    const { getByText, getByTestId } = render(
      <AppSentenceBuilder
        template="I entered on {entry} with a {visa} visa."
        fields={{
          entry: <input data-testid="field-entry" type="date" defaultValue="2026-04-01" />,
          visa: <select data-testid="field-visa"><option>E33G</option></select>,
        }}
      />,
    );
    expect(getByText(/I entered on/)).toBeTruthy();
    expect(getByText(/with a/)).toBeTruthy();
    expect(getByText(/visa\./)).toBeTruthy();
    expect(getByTestId("field-entry")).toBeTruthy();
    expect(getByTestId("field-visa")).toBeTruthy();
  });

  it("renders nothing if template is empty", () => {
    const { container } = render(<AppSentenceBuilder template="" fields={{}} />);
    expect(container.firstChild?.textContent).toBe("");
  });

  it("leaves unknown placeholders visible as-is", () => {
    const { getByText } = render(
      <AppSentenceBuilder
        template="Fill {missing} please."
        fields={{ other: <span>x</span> }}
      />,
    );
    // placeholder left literal so developers can see the problem
    expect(getByText(/\{missing\}/)).toBeTruthy();
  });
});

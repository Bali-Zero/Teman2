import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Landmark, Home, Scale } from "lucide-react";
import { QuestionCard, OptionButton } from "./QuestionCard";

describe("QuestionCard > OptionButton icon support", () => {
  it("renders an icon when the icon prop is provided", () => {
    const { container } = render(
      <OptionButton
        label="Bank deposit"
        selected={false}
        onSelect={vi.fn()}
        variant="radio"
        icon={Landmark}
      />,
    );

    const icon = container.querySelector("svg[aria-hidden='true']");
    expect(icon).toBeInTheDocument();
  });

  it("keeps the label text when an icon is present", () => {
    render(
      <OptionButton
        label="Completed strata-title property"
        selected={false}
        onSelect={vi.fn()}
        variant="radio"
        icon={Home}
      />,
    );

    expect(
      screen.getByRole("radio", { name: "Completed strata-title property" }),
    ).toBeInTheDocument();
  });

  it("marks the icon aria-hidden so the accessible name comes from the label", () => {
    const { container } = render(
      <OptionButton
        label="I am not sure yet"
        selected={false}
        onSelect={vi.fn()}
        variant="radio"
        icon={Scale}
      />,
    );

    const icon = container.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });

  it("does not render an icon when the icon prop is omitted", () => {
    const { container } = render(
      <OptionButton
        label="Under 55"
        selected={false}
        onSelect={vi.fn()}
        variant="radio"
      />,
    );

    expect(container.querySelector("svg")).not.toBeInTheDocument();
  });

  it("does not add icons to non-route QuestionCard options by default", () => {
    const { container } = render(
      <QuestionCard
        heading="First, how old are you?"
        body="Age helps determine routes."
        why="Regulation uses different thresholds."
        options={[
          <OptionButton
            key="under_55"
            label="Under 55"
            selected={false}
            onSelect={vi.fn()}
            variant="radio"
          />,
          <OptionButton
            key="60_plus"
            label="60 or over"
            selected={false}
            onSelect={vi.fn()}
            variant="radio"
          />,
        ]}
      >
        <button type="button">Continue</button>
      </QuestionCard>,
    );

    expect(container.querySelectorAll("svg").length).toBe(1); // only the chevron in <details>
  });
});

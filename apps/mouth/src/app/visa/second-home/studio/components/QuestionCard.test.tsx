import { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Landmark, Home, Scale } from "lucide-react";
import { QuestionCard, OptionButton } from "./QuestionCard";

const RADIO_LABELS = ["55–59", "60 or over", "Under 55"] as const;

function RadioQuestion() {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <QuestionCard
      heading="First, how old are you?"
      body="Age helps determine routes."
      why="Regulation uses different thresholds."
      options={RADIO_LABELS.map((label) => (
        <OptionButton
          key={label}
          label={label}
          selected={selected === label}
          onSelect={() => setSelected(label)}
          variant="radio"
        />
      ))}
    >
      <button type="button">Continue</button>
    </QuestionCard>
  );
}

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

describe("QuestionCard > OptionButton selection control", () => {
  it("keeps selected and unselected option borders the same thickness and gives focus a separate non-layout ring", () => {
    const { container } = render(<RadioQuestion />);
    const first = screen.getAllByRole("radio")[0];

    fireEvent.click(first);

    const css = container.querySelector("style")?.textContent ?? "";
    const baseRule = css.match(/\.bz-shs-option\s*\{([^}]*)\}/s)?.[1] ?? "";
    const selectedRule =
      css.match(
        /\.bz-shs-option\[data-selected="true"\]\s*\{([^}]*)\}/s,
      )?.[1] ?? "";
    expect(baseRule).toMatch(/border:\s*1px solid/);
    expect(selectedRule).not.toMatch(/(?:^|;)\s*border\s*:/);
    expect(selectedRule).not.toMatch(/border-width\s*:/);
    // Ink, not red: R4 §3/§4.5 gives red exactly two duties (structure and
    // action) and selection is neither — a chosen option is an ink outline.
    // The thickness assertions above are the ones guarding against layout
    // shift; this line only pins WHICH colour the outline takes.
    expect(selectedRule).toMatch(/border-color:\s*var\(--text-primary\)/);
    expect(selectedRule).not.toMatch(/var\(--accent-funnel\)/);
    expect(css).toMatch(
      /\.bz-shs-option\[data-selected="true"\]\s*\{[^}]*box-shadow:\s*inset 0 0 0 2px/s,
    );
    expect(css).toMatch(
      /\.bz-shs-option:focus-visible\s*\{[^}]*outline:\s*3px solid[^}]*outline-offset:\s*3px/s,
    );
    expect(css).toMatch(
      /@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*\.bz-shs-option[\s\S]*transition:\s*none/s,
    );
  });

  it("keeps exactly one radio in the tab order and moves tabindex=0 with selection", () => {
    render(<RadioQuestion />);
    const radios = screen.getAllByRole("radio");

    expect(radios.map((radio) => radio.getAttribute("tabindex"))).toEqual([
      "0",
      "-1",
      "-1",
    ]);

    fireEvent.click(radios[1]);

    expect(radios.map((radio) => radio.getAttribute("tabindex"))).toEqual([
      "-1",
      "0",
      "-1",
    ]);
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
  });

  it("moves focus and selection with arrows, Home, and End, including wrapping", () => {
    render(<RadioQuestion />);

    const expectKeyboardMove = (key: string, expectedIndex: number) => {
      const radios = screen.getAllByRole("radio");
      fireEvent.keyDown(document.activeElement as HTMLElement, { key });
      expect(document.activeElement).toBe(radios[expectedIndex]);
      expect(radios[expectedIndex]).toHaveAttribute("aria-checked", "true");
      expect(radios[expectedIndex]).toHaveAttribute("tabindex", "0");
      expect(
        radios.filter((radio) => radio.getAttribute("tabindex") === "0"),
      ).toHaveLength(1);
    };

    screen.getAllByRole("radio")[0].focus();
    expectKeyboardMove("ArrowDown", 1);
    expectKeyboardMove("ArrowUp", 0);
    expectKeyboardMove("ArrowUp", 2);
    expectKeyboardMove("ArrowDown", 0);
    expectKeyboardMove("End", 2);
    expectKeyboardMove("Home", 0);
    expectKeyboardMove("ArrowRight", 1);
    expectKeyboardMove("ArrowLeft", 0);
  });

  it("leaves toggle buttons as independent Tab stops and does not capture arrow keys", () => {
    const firstToggle = vi.fn();
    const secondToggle = vi.fn();
    render(
      <QuestionCard
        heading="Who would you want to include?"
        body="Choose any family members."
        why="Each family member has a separate route."
      >
        <OptionButton label="Spouse" selected={false} onSelect={firstToggle} />
        <OptionButton
          label="Children"
          selected={false}
          onSelect={secondToggle}
        />
      </QuestionCard>,
    );

    const toggles = screen.getAllByRole("button", {
      name: /Spouse|Children/,
    });
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(toggles.map((toggle) => toggle.tabIndex)).toEqual([0, 0]);

    toggles[0].focus();
    fireEvent.keyDown(toggles[0], { key: "ArrowDown" });

    expect(document.activeElement).toBe(toggles[0]);
    expect(firstToggle).not.toHaveBeenCalled();
    expect(secondToggle).not.toHaveBeenCalled();
  });
});

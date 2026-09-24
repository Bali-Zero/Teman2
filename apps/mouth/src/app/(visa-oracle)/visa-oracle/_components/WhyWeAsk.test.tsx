import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { WhyWeAsk } from "./WhyWeAsk";

const factMapping = {
  kind: "FACT" as const,
  factPaths: ["immigration.currently_in_indonesia"],
};
const whyText =
  "Your current location tells the engine whether this is an onshore situation or a future plan.";

describe("WhyWeAsk", () => {
  it("renders inline content without an expandable control", () => {
    render(
      <WhyWeAsk
        language="en"
        i18nKey="why.in_indonesia"
        decisionMapping={factMapping}
        variant="inline"
      />,
    );

    expect(screen.getByText(whyText)).toBeInTheDocument();
    expect(
      screen.queryByLabelText(/why we ask this question/i),
    ).not.toBeInTheDocument();
    expect(document.querySelector("[aria-expanded]")).toBeNull();
  });

  it("keeps the default disclosure closed until its trigger is clicked", async () => {
    const user = userEvent.setup();
    render(
      <WhyWeAsk
        language="en"
        i18nKey="why.in_indonesia"
        decisionMapping={factMapping}
      />,
    );

    const trigger = screen.getByRole("button", {
      name: "Why we ask this question",
    });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(whyText)).not.toBeInTheDocument();

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(whyText)).toBeInTheDocument();
  });
});

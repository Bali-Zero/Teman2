import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { LivingTree } from "./LivingTree";

describe("LivingTree visible breadcrumb", () => {
  it("shows the current branch and lets keyboard users edit a completed fact", async () => {
    const user = userEvent.setup();
    const onEditQuestion = vi.fn();
    render(
      <LivingTree
        language="en"
        current={{ kind: "question", questionId: "nationalities" }}
        facts={{ in_indonesia: "no", overstay_days: "0" }}
        onEditQuestion={onEditQuestion}
      />,
    );

    const breadcrumb = screen.getByRole("navigation", {
      name: "Current interview branch",
    });
    expect(within(breadcrumb).getByText("Passports")).toHaveAttribute(
      "aria-current",
      "step",
    );
    const edit = within(breadcrumb).getByRole("button", {
      name: "Edit answer: Active overstay",
    });
    edit.focus();
    await user.keyboard("{Enter}");
    expect(onEditQuestion).toHaveBeenCalledWith("overstay_days");
  });
});

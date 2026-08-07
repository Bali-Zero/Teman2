import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { QUESTIONS } from "../_lib/tree";
import { QuestionScreen } from "./QuestionScreen";

function renderNationalities(currentAnswer?: string) {
  const onAnswer = vi.fn();
  const onSkip = vi.fn();
  render(
    <QuestionScreen
      language="en"
      question={QUESTIONS.nationalities}
      onAnswer={onAnswer}
      onSkip={onSkip}
      onBack={vi.fn()}
      canGoBack
      currentAnswer={currentAnswer}
    />,
  );
  return { onAnswer, onSkip };
}

describe("QuestionScreen country picker", () => {
  it("uses localized country names, supports keyboard add/remove, and persists sorted alpha-2 codes", async () => {
    const user = userEvent.setup();
    const { onAnswer } = renderNationalities();
    const picker = screen.getByLabelText("Passport countries");

    await user.selectOptions(picker, "IT");
    await user.tab();
    const add = screen.getByRole("button", { name: "Add country" });
    expect(add).toHaveFocus();
    await user.keyboard("{Enter}");

    const selected = screen.getByRole("list", { name: "Selected countries" });
    expect(within(selected).getByText(/Italy \(IT\)/)).toBeInTheDocument();
    const removeItaly = screen.getByRole("button", { name: "Remove Italy" });
    removeItaly.focus();
    await user.keyboard("{Enter}");
    expect(
      screen.queryByRole("list", { name: "Selected countries" }),
    ).not.toBeInTheDocument();

    await user.selectOptions(picker, "IT");
    await user.click(add);
    await user.selectOptions(picker, "ID");
    await user.click(add);
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(onAnswer).toHaveBeenCalledWith("ID,IT");
  });

  it("maps Other / not listed to unsure instead of inventing a country code", async () => {
    const user = userEvent.setup();
    const { onAnswer, onSkip } = renderNationalities("ID");

    await user.selectOptions(
      screen.getByLabelText("Passport countries"),
      "not-listed",
    );

    expect(onSkip).toHaveBeenCalledTimes(1);
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("accepts four passport countries and blocks a fifth before the wire boundary", async () => {
    const user = userEvent.setup();
    const { onAnswer } = renderNationalities();
    const picker = screen.getByLabelText("Passport countries");
    const add = screen.getByRole("button", { name: "Add country" });

    for (const code of ["AU", "FR", "ID", "IT"]) {
      await user.selectOptions(picker, code);
      await user.click(add);
    }

    expect(add).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "You can add up to 4 passport countries",
    );
    await user.selectOptions(picker, "US");
    expect(add).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(onAnswer).toHaveBeenCalledWith("AU,FR,ID,IT");
  });

  it("restores valid selected countries as removable chips", () => {
    renderNationalities("ID,IT");
    expect(
      screen.getByRole("button", { name: "Remove Indonesia" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove Italy" }),
    ).toBeInTheDocument();
  });
});

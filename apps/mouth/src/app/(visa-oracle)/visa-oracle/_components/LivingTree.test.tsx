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

describe("LivingTree sr-only progress nav (category answered 'Not sure?')", () => {
  // Live defect, measured on balizero.com/visa-oracle: at the length-of-stay
  // step, after answering "category" with the NotSure affordance
  // (facts.category === "unsure" — flowReducer's SKIP action, a real,
  // reachable interview path, tree.ts `notSure: { mode: "human-review" }`),
  // `nav.oracle-sr-only` rendered as a completely empty `<ol>` and the step
  // never reappeared in later steps' trail. `getTreeSteps` (flow.ts) never
  // takes a language, so the mechanism is not translation-specific — GUILT
  // reproduces on the Indonesian interface as measured; INNOCENCE pins
  // that English's already-correct rendering (both the ordinary "unsure"
  // case and a ordinary answered-category case) is unaffected by the fix.
  const UNSURE_CATEGORY_FACTS = {
    in_indonesia: "no",
    overstay_days: "0",
    nationalities: "IT",
    birth_date: "1990-02-03",
    category: "unsure",
    trip_scope: "single",
  };
  const current = { kind: "question" as const, questionId: "stay_days" };

  it("GUILT: the Indonesian sr-only nav names the current step instead of rendering empty", () => {
    render(
      <LivingTree
        language="id"
        current={current}
        facts={UNSURE_CATEGORY_FACTS}
        onEditQuestion={vi.fn()}
      />,
    );
    const srNav = screen.getByRole("navigation", {
      name: "Jalur Anda sejauh ini",
    });
    expect(srNav.textContent).not.toBe("");
    expect(within(srNav).getByText(/Lama tinggal/)).toBeInTheDocument();
    expect(within(srNav).getByText(/langkah saat ini/)).toBeInTheDocument();
  });

  it("INNOCENCE: the English sr-only nav is unaffected — both under the same 'unsure' facts and on the ordinary answered-category path", () => {
    const { unmount } = render(
      <LivingTree
        language="en"
        current={current}
        facts={UNSURE_CATEGORY_FACTS}
        onEditQuestion={vi.fn()}
      />,
    );
    const srNavUnsure = screen.getByRole("navigation", {
      name: "Your path so far",
    });
    expect(srNavUnsure.textContent).not.toBe("");
    expect(within(srNavUnsure).getByText(/Length of stay/)).toBeInTheDocument();
    unmount();

    // Regression pin: an ordinary, already-answered category (not "unsure")
    // — the shape every prior test in this file exercised — must render
    // identically to before this fix.
    render(
      <LivingTree
        language="en"
        current={current}
        facts={{ ...UNSURE_CATEGORY_FACTS, category: "tourism" }}
        onEditQuestion={vi.fn()}
      />,
    );
    const srNavReal = screen.getByRole("navigation", {
      name: "Your path so far",
    });
    expect(
      within(srNavReal).getByText(/Length of stay: current step/),
    ).toBeInTheDocument();
  });
});

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

describe("LivingTree jump sheet (W-VO-T)", () => {
  const FACTS = {
    in_indonesia: "no",
    holds_stay_permit: "no",
    overstay_days: "0",
    nationalities: "IT",
    birth_date: "1990-02-03",
    category: "work",
    trip_scope: "single",
  };
  const current = { kind: "question" as const, questionId: "work_payer" };

  it("every answered question is a jump target that carries the answer itself", async () => {
    const user = userEvent.setup();
    const onEditQuestion = vi.fn();
    const { container } = render(
      <LivingTree
        language="en"
        current={current}
        facts={FACTS}
        onEditQuestion={onEditQuestion}
      />,
    );
    const panel = container.querySelector<HTMLElement>(
      '[data-process-part="progress"][data-process-rail="desktop"]',
    )?.parentElement;
    if (!panel) throw new Error("no desktop tree panel");

    // Not only the last four the breadcrumb shows: the whole answered path.
    const jumps = panel.querySelectorAll("[data-process-jump]");
    expect(jumps.length).toBeGreaterThanOrEqual(7);

    const target = within(panel).getByRole("button", {
      name: "Jump back to Category — you answered Work & employment",
    });
    await user.click(target);
    expect(onEditQuestion).toHaveBeenCalledWith("category");
  });

  it("the mobile progress line carries the step count and the open category", () => {
    render(
      <LivingTree
        language="en"
        current={current}
        facts={FACTS}
        onEditQuestion={vi.fn()}
      />,
    );
    const trigger = screen.getByRole("button", { expanded: false });
    expect(trigger.textContent).toContain("Your path so far");
    expect(trigger.textContent).toMatch(/\d+ of \d+ answered/);
    expect(trigger.textContent).toContain("Work & employment");
  });

  it("announces the branches an answer closed, exactly once", () => {
    const { container } = render(
      <LivingTree
        language="en"
        current={current}
        facts={FACTS}
        onEditQuestion={vi.fn()}
      />,
    );
    const announcers = container.querySelectorAll("[data-process-announce]");
    expect(announcers).toHaveLength(1);
    expect(announcers[0].textContent).toBe(
      "You chose Work & employment. 10 of the other purpose branches closed.",
    );
  });
});

describe("LivingTree at a follow-up question (W-VO-T, council round 2)", () => {
  // codex-gpt-5.6-sol: the corrected trunk lived only inside the progress
  // line, so at an appended follow-up the trunk beside it still painted
  // every step "pending" — and every jump target disappeared, exactly when
  // a visitor most wants to correct an answer.
  const FACTS = {
    in_indonesia: "no",
    holds_stay_permit: "no",
    overstay_days: "0",
    nationalities: "IT",
    birth_date: "1985-04-12",
    category: "tourism",
    trip_scope: "single",
    stay_days: "30",
    entry_pattern: "SINGLE",
    review_gate: "none",
  };

  it("keeps every answered question reachable", () => {
    const { container } = render(
      <LivingTree
        language="en"
        current={{ kind: "question", questionId: "family_sponsor_confirmed" }}
        facts={FACTS}
        onEditQuestion={vi.fn()}
        visitedVerdict
      />,
    );
    const desktop = container.querySelector<HTMLElement>(
      '[data-process-part="progress"][data-process-rail="desktop"]',
    )?.parentElement;
    if (!desktop) throw new Error("no desktop tree panel");
    expect(
      desktop.querySelectorAll("[data-process-jump]").length,
    ).toBeGreaterThanOrEqual(Object.keys(FACTS).length);
    expect(
      desktop.querySelector('[data-process-jump="category"]'),
    ).not.toBeNull();
  });
});

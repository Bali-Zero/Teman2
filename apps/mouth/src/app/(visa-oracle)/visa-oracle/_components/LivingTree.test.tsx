import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { LivingTree } from "./LivingTree";
import { dict, translate, type I18nKey } from "../_lib/i18n";

describe("LivingTree branch previews (C2-1)", () => {
  const facts = {
    in_indonesia: "no",
    holds_stay_permit: "no",
    overstay_days: "0",
    nationalities: "IT",
    birth_date: "1990-02-03",
    category: "work",
    trip_scope: "single",
  };

  it("projects another category from its hypothetical route without raw i18n keys", () => {
    const { container } = render(
      <LivingTree
        language="en"
        current={{ kind: "question", questionId: "work_payee" }}
        facts={facts}
        onEditQuestion={vi.fn()}
      />,
    );
    const invest = container.querySelector(
      '[data-process-branch-preview="invest"]',
    );
    expect(invest).not.toBeNull();
    expect(invest).toHaveTextContent("Investment basis");
    expect(
      container.querySelectorAll("[data-process-branch-preview]"),
    ).not.toHaveLength(0);
    for (const preview of container.querySelectorAll(
      "[data-process-branch-preview]",
    )) {
      expect(preview.textContent).not.toMatch(/^tree\./m);
    }
  });

  it("GUILT-b: the dict-membership filter is load-bearing on a genuinely unlabelled id", () => {
    // C2-4 happens to translate all three ids that were unlabelled before
    // this PR (`tree.investment_currency`, `tree.investment_amount_usd`,
    // `tree.retirement_undecided_basis` — see i18n.ts and DRAFT-SPEC-C2-1.v2
    // F11), which is why a route through those ids no longer exposes a raw
    // `/^tree\./` label against the SHIPPED dict — the filter is never
    // exercised. `dict.en`/`dict.id` are plain objects at runtime (`as
    // const` is TS-only, never `Object.freeze`d), so this test deletes one
    // entry to reproduce the pre-fix state the filter exists for, asserts
    // the shipped component still drops the id into the remainder (never
    // its own raw key), and restores the entry in `finally` so no other
    // test in this file observes the mutation.
    const investRoute = {
      ...facts,
      // Puts `investment_currency` inside the "invest" preview's first 4
      // unseen ids (measured: `investment_vehicle`, `investment_currency`,
      // `investment_establishes_company`, `investment_foreign_branch`,
      // with `family_sponsor_confirmed` and `wants_onshore_conversion`
      // folded into the remainder) — a leftover fact from an abandoned
      // "invest" branch is a legitimate `OracleFacts` shape even while
      // `category` reads "work": `pruneFacts` only ever narrows facts on
      // the reducer's own write path, never on this pure read of an
      // arbitrary facts object.
      investment_vehicle: "merit",
    };
    const original = dict.en["tree.investment_currency"];
    delete (dict.en as Record<string, string>)["tree.investment_currency"];
    try {
      const { container } = render(
        <LivingTree
          language="en"
          current={{ kind: "question", questionId: "work_payee" }}
          facts={investRoute}
          onEditQuestion={vi.fn()}
        />,
      );
      const invest = container.querySelector(
        '[data-process-branch-preview="invest"]',
      );
      expect(invest).not.toBeNull();
      expect(invest!.textContent).not.toMatch(/tree\.investment_currency/);
      for (const preview of container.querySelectorAll(
        "[data-process-branch-preview]",
      )) {
        expect(preview.textContent).not.toMatch(/^tree\./m);
      }
    } finally {
      (dict.en as Record<string, string>)["tree.investment_currency"] =
        original;
    }
  });

  it("does not render previews before a category is available", () => {
    const { category: _category, ...factsWithoutCategory } = facts;
    const { container } = render(
      <LivingTree
        language="en"
        current={{ kind: "question", questionId: "category" }}
        facts={factsWithoutCategory}
        onEditQuestion={vi.fn()}
      />,
    );
    expect(
      container.querySelectorAll("[data-process-branch-preview]"),
    ).toHaveLength(0);
  });

  it("resolves every C2-4 key in both languages", () => {
    render(
      <LivingTree
        language="en"
        current={{ kind: "question", questionId: "work_payee" }}
        facts={facts}
        onEditQuestion={vi.fn()}
      />,
    );
    const keys = [
      "process.branch_preview_more",
      "process.branch_reopen_aria",
      "tree.investment_currency",
      "tree.investment_amount_usd",
      "tree.retirement_undecided_basis",
    ] as const;
    for (const key of keys) {
      expect(translate("en", key as I18nKey)).not.toBe(key);
      expect(translate("id", key as I18nKey)).not.toBe(key);
    }
  });
});

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
  // Council round finding: the corrected trunk lived only inside the progress
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

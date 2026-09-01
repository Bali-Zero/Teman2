import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { usePricingData } from "@/hooks/usePricingData";
import {
  emptyPlan,
  encodePlanFragment,
  savePlan,
  PLAN_STORAGE_KEY,
} from "@/lib/secondhome-studio/plan-codec";
import type { PlanState } from "@/lib/secondhome-studio/types";
import { StudioApp } from "./StudioApp";

/**
 * Second Home Studio — wizard + verdict-page smoke tests (spec §7.1-ish for
 * the UI layer; the lib's own __tests__/ pin the decision table/codec/copy
 * sweep independently). Covers, at minimum, the scenarios the conductor
 * asked for: full happy path -> strong fit, 55-59 -> edge case + disclosure,
 * property -> edge case (never "strong match"), checklist toggle updates
 * the meter, fragment-load lands on verdict, malformed fragment -> first
 * question — plus the fix-mandate round-1 additions: P1-C6 (malformed
 * fragment must not resurrect an old localStorage plan), P2-3 (focus moves
 * to the new stage heading on step transitions), P2-4 (radiogroup/radio
 * roles on single-select steps), P1-C9 (CustodyMap conditional on
 * verdict.product).
 */

vi.mock("@/hooks/usePricingData", () => ({
  usePricingData: vi.fn(),
}));

function mockPrice(price: string | null) {
  vi.mocked(usePricingData).mockReturnValue({
    price,
    isLoading: false,
    isError: false,
  });
}

/** Single-select options render as role="radio" (P2-4); nav buttons and
 *  the family step's multi-select toggles stay role="button". Try both so
 *  every existing call site keeps working unchanged. */
function clickButton(name: string) {
  const el =
    screen.queryByRole("button", { name }) ??
    screen.queryByRole("radio", { name });
  if (!el) {
    throw new Error(`No button or radio option found with name "${name}"`);
  }
  fireEvent.click(el);
}

function fullPlan(overrides: Partial<PlanState> = {}): PlanState {
  return {
    ...emptyPlan(),
    age: "under_55",
    route: "deposit",
    capital: "ready_130k",
    family: { spouse: false, children: 0, parents: 0 },
    horizon: "asap",
    location: "in_indonesia",
    ...overrides,
  };
}

describe("StudioApp", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.location.hash = "";
    mockPrice("IDR 35,000,000");
  });

  afterEach(() => {
    window.location.hash = "";
  });

  it("full happy path (under_55 + deposit + ready_130k) renders a strong-fit verdict with the Imigrasi sentence", async () => {
    render(<StudioApp />);

    expect(
      screen.getByRole("heading", { name: /how old are you/i }),
    ).toBeInTheDocument();

    clickButton("Under 55");
    clickButton("Continue");

    clickButton("Bank deposit");
    clickButton("Continue");

    clickButton("USD 130,000 is ready");
    clickButton("Continue");

    // Family: no selections, just proceed.
    clickButton("Continue");

    clickButton("As soon as possible");
    clickButton("Continue");

    clickButton("In Indonesia");
    clickButton("See your fit-check result");

    expect(
      await screen.findByRole("heading", { name: /strong match/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/rests with Imigrasi/)).toBeInTheDocument();
  });

  it("55-59 path always lands on an edge-case verdict with the age disclosure note", async () => {
    render(<StudioApp />);

    clickButton("55–59");
    clickButton("Continue");

    clickButton("Bank deposit");
    clickButton("Continue");

    clickButton("USD 50,000 deposit plus USD 3,000 monthly income");
    clickButton("Continue");

    clickButton("Continue"); // family
    clickButton("This quarter");
    clickButton("Continue");
    clickButton("Outside Indonesia");
    clickButton("See your fit-check result");

    expect(
      await screen.findByRole("heading", { name: /needs human review/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Indonesian regulation states this age threshold differently/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /strong match/i })).toBeNull();
  });

  it("property route always lands on edge-case — 'strong match' never appears", async () => {
    render(<StudioApp />);

    clickButton("Under 55");
    clickButton("Continue");

    clickButton("Completed strata-title property");
    clickButton("Continue");

    clickButton("I do not have a property route");
    clickButton("Continue");

    clickButton("Continue"); // family
    clickButton("I am still exploring");
    clickButton("Continue");
    clickButton("In Indonesia");
    clickButton("See your fit-check result");

    expect(
      await screen.findByRole("heading", { name: /needs human review/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/strong match/i)).toBeNull();
  });

  it("checklist toggle updates the readiness meter", async () => {
    // fullPlan() is a deposit-route, no-family plan: 7 of the 10 items apply
    // (property_documents, passive_income_evidence and family_records read
    // "may also apply" for this route/family combination — see
    // checklist.ts's classifyChecklistItem) — the meter's denominator
    // reflects only the applicable group, never the full union.
    window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
    render(<StudioApp />);

    expect(await screen.findByText(/0 of 7 prepared/)).toBeInTheDocument();

    // All 10 items still render as checkboxes (both groups stay visible AND
    // tickable) — only the meter narrows, nothing is hidden or deleted.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(10);
    fireEvent.click(checkboxes[0]); // first item in the "applies" group

    expect(await screen.findByText(/1 of 7 prepared/)).toBeInTheDocument();
  });

  it("a crafted valid #p= fragment lands directly on the verdict page", async () => {
    window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
    render(<StudioApp />);

    expect(
      await screen.findByRole("heading", { name: /strong match/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /how old are you/i }),
    ).toBeNull();
  });

  it("a malformed fragment falls back to a fresh plan on the first question", async () => {
    window.location.hash = "#p=thisisnotvalidjsononcedecoded";
    render(<StudioApp />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /how old are you/i }),
      ).toBeInTheDocument();
    });
  });

  it("P1-C6: a malformed fragment does NOT resurrect an old localStorage plan — a PRESENT fragment always wins, even invalid", async () => {
    savePlan(fullPlan()); // an old saved strong-fit-eligible plan
    window.location.hash = "#p=thisisnotvalidjsononcedecoded";
    render(<StudioApp />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /how old are you/i }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: /strong match/i })).toBeNull();
  });

  it("renders no price block when usePricingData abstains (null)", async () => {
    mockPrice(null);
    window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
    render(<StudioApp />);

    await screen.findByRole("heading", { name: /strong match/i });
    expect(screen.queryByText("Your all-inclusive figure")).toBeNull();
  });

  describe("P2-3 — focus moves to the new stage heading on step transitions", () => {
    it("moves focus to the route heading after clicking Continue on the age step", async () => {
      render(<StudioApp />);

      clickButton("Under 55");
      clickButton("Continue");

      await waitFor(() => {
        expect(document.activeElement).toBe(
          screen.getByRole("heading", {
            name: /which route are you considering/i,
          }),
        );
      });
    });

    it("moves focus to the verdict heading after the final user-driven Continue click", async () => {
      render(<StudioApp />);

      clickButton("Under 55");
      clickButton("Continue");
      clickButton("Bank deposit");
      clickButton("Continue");
      clickButton("USD 130,000 is ready");
      clickButton("Continue");
      clickButton("Continue"); // family
      clickButton("As soon as possible");
      clickButton("Continue");
      clickButton("In Indonesia");
      clickButton("See your fit-check result");

      await waitFor(() => {
        expect(document.activeElement).toBe(
          screen.getByRole("heading", { name: /strong match/i }),
        );
      });
    });

    it("does not steal focus on initial mount (first question heading is not auto-focused)", () => {
      render(<StudioApp />);
      const heading = screen.getByRole("heading", {
        name: /how old are you/i,
      });
      expect(document.activeElement).not.toBe(heading);
    });

    it("does not steal focus on a hydration jump straight to the verdict page (a saved link is not a user click)", async () => {
      window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
      render(<StudioApp />);
      const heading = await screen.findByRole("heading", {
        name: /strong match/i,
      });
      expect(document.activeElement).not.toBe(heading);
    });
  });

  describe("P2-4 — single-select steps expose radiogroup/radio roles; family stays multi-select", () => {
    it("the age step's options render as a radiogroup of radio buttons", () => {
      render(<StudioApp />);
      expect(screen.getByRole("radiogroup")).toBeInTheDocument();
      const radios = screen.getAllByRole("radio");
      expect(radios).toHaveLength(3);
      for (const radio of radios) {
        expect(radio).toHaveAttribute("aria-checked");
      }
    });

    it("selecting a radio option updates aria-checked", () => {
      render(<StudioApp />);
      clickButton("Under 55");
      expect(screen.getByRole("radio", { name: "Under 55" })).toHaveAttribute(
        "aria-checked",
        "true",
      );
      expect(screen.getByRole("radio", { name: "55–59" })).toHaveAttribute(
        "aria-checked",
        "false",
      );
    });

    it("the family step (multi-select) has no radiogroup and uses aria-pressed toggle buttons", async () => {
      render(<StudioApp />);
      clickButton("Under 55");
      clickButton("Continue");
      clickButton("Bank deposit");
      clickButton("Continue");
      clickButton("USD 130,000 is ready");
      clickButton("Continue");

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /who would you want/i }),
        ).toBeInTheDocument();
      });
      expect(screen.queryByRole("radiogroup")).toBeNull();
      expect(screen.queryByRole("radio")).toBeNull();
      const spouse = screen.getByRole("button", { name: "Spouse" });
      expect(spouse).toHaveAttribute("aria-pressed", "false");
      fireEvent.click(spouse);
      expect(spouse).toHaveAttribute("aria-pressed", "true");
    });
  });

  describe("Continue gating (2026-08-20 design pass) — disabled until the step's question is answered", () => {
    it("guilt: the age step's Continue is disabled before any option is selected", () => {
      render(<StudioApp />);
      expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    });

    it("innocence: selecting an option enables Continue on that same step", () => {
      render(<StudioApp />);
      clickButton("Under 55");
      expect(
        screen.getByRole("button", { name: "Continue" }),
      ).not.toBeDisabled();
    });

    it("guilt: Continue re-disables on the NEXT step until it too is answered (per-step state, not sticky)", async () => {
      render(<StudioApp />);
      clickButton("Under 55");
      clickButton("Continue");

      await waitFor(() => {
        expect(
          screen.getByRole("heading", {
            name: /which route are you considering/i,
          }),
        ).toBeInTheDocument();
      });
      expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();

      clickButton("Bank deposit");
      expect(
        screen.getByRole("button", { name: "Continue" }),
      ).not.toBeDisabled();
    });

    it("innocence: the family step (multi-select, always answered) has Continue enabled with zero selections", async () => {
      render(<StudioApp />);
      clickButton("Under 55");
      clickButton("Continue");
      clickButton("Bank deposit");
      clickButton("Continue");
      clickButton("USD 130,000 is ready");
      clickButton("Continue");

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /who would you want/i }),
        ).toBeInTheDocument();
      });
      expect(
        screen.getByRole("button", { name: "Continue" }),
      ).not.toBeDisabled();
    });

    it("guilt: clicking a disabled Continue does not advance the step (fireEvent.click on a disabled button is a no-op)", () => {
      render(<StudioApp />);
      fireEvent.click(screen.getByRole("button", { name: "Continue" }));
      expect(
        screen.getByRole("heading", { name: /how old are you/i }),
      ).toBeInTheDocument();
    });
  });

  describe("P1-C9 — CustodyMap renders only for deposit-holding verdicts (E33/E33E)", () => {
    it("under_55 deposit strong_fit (E33): CustodyMap renders", async () => {
      window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
      render(<StudioApp />);
      await screen.findByRole("heading", { name: /strong match/i });
      expect(screen.getByText("Your money stays yours")).toBeInTheDocument();
    });

    it("60_plus income-only strong_fit (E33F): CustodyMap does NOT render", async () => {
      window.location.hash = `#p=${encodePlanFragment(
        fullPlan({
          age: "60_plus",
          capital: null,
          seniorFunding: "income_only_3k",
        }),
      )}`;
      render(<StudioApp />);
      await screen.findByRole("heading", { name: /strong match/i });
      expect(screen.queryByText("Your money stays yours")).toBeNull();
    });

    it("property route edge_case (no product): CustodyMap does NOT render", async () => {
      window.location.hash = `#p=${encodePlanFragment(
        fullPlan({
          route: "property",
          capital: null,
          property: "none",
        }),
      )}`;
      render(<StudioApp />);
      await screen.findByRole("heading", { name: /needs human review/i });
      expect(screen.queryByText("Your money stays yours")).toBeNull();
    });

    it("60_plus deposit strong_fit (E33E): CustodyMap renders", async () => {
      window.location.hash = `#p=${encodePlanFragment(
        fullPlan({
          age: "60_plus",
          capital: null,
          seniorFunding: "deposit_50k_income",
        }),
      )}`;
      render(<StudioApp />);
      await screen.findByRole("heading", { name: /strong match/i });
      expect(screen.getByText("Your money stays yours")).toBeInTheDocument();
    });
  });

  describe("Print layout fix (2026-08-24) — verdict-stage nav control is print-hidden", () => {
    it("the 'Back to your answers' control is wrapped in the class SavePlanBar's print stylesheet hides", async () => {
      window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
      render(<StudioApp />);
      const backButton = await screen.findByRole("button", {
        name: /back to your answers/i,
      });

      // Behavioural, not source-text: this proves the actual DOM node the
      // print stylesheet's `.bz-shs-back-to-answers { display: none }`
      // selector (see SavePlanBar's PRINT_STYLES) targets really exists
      // and really wraps this control — not just that some string with
      // that name appears somewhere in a CSS blob.
      expect(backButton.closest(".bz-shs-back-to-answers")).not.toBeNull();
    });
  });

  describe("S13 verdict-crown — exactly one <h1> at every stage", () => {
    it("question stage: exactly one <h1>, and its text is the page masthead 'Check your fit'", () => {
      const { container } = render(<StudioApp />);
      const h1s = container.querySelectorAll("h1");
      expect(h1s).toHaveLength(1);
      expect(h1s[0]).toHaveTextContent("Check your fit");
    });

    it("verdict stage: exactly one <h1>, and its text is the verdict heading — not 'Check your fit'", async () => {
      window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
      const { container } = render(<StudioApp />);
      await screen.findByRole("heading", { name: /strong match/i });

      const h1s = container.querySelectorAll("h1");
      expect(h1s).toHaveLength(1);
      expect(h1s[0]).toHaveTextContent(/strong match/i);
      expect(h1s[0]).not.toHaveTextContent("Check your fit");
    });

    it("verdict stage: 'Check your fit' is still present (demoted, not deleted) but is not a heading element", async () => {
      window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
      render(<StudioApp />);
      await screen.findByRole("heading", { name: /strong match/i });

      const masthead = screen.getByText("Check your fit");
      expect(masthead).toBeInTheDocument();
      expect(masthead.closest("h1,h2,h3,h4,h5,h6")).toBeNull();
    });

    it("verdict stage: the demoted masthead label is Inter 600, not Cormorant, at its 1.05rem (16.8px) size — below the R4 §3 24px display floor", async () => {
      window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
      render(<StudioApp />);
      await screen.findByRole("heading", { name: /strong match/i });

      const masthead = screen.getByText("Check your fit");
      const styleAttr = masthead.getAttribute("style") ?? "";
      const fontFamily = styleAttr.match(/font-family:\s*([^;]+)/)?.[1]?.trim();
      const fontSize = styleAttr.match(/font-size:\s*([^;]+)/)?.[1]?.trim();
      const fontWeight = styleAttr.match(/font-weight:\s*([^;]+)/)?.[1]?.trim();

      expect(fontFamily).toBe(
        "var(--font-sans, ui-sans-serif, system-ui, sans-serif)",
      );
      expect(fontSize).toBe("1.05rem");
      expect(fontWeight).toBe("600");
    });
  });

  describe("ScenarioToggle — saved-plan immutability", () => {
    it("opening the route preview does not mutate the saved plan in localStorage", async () => {
      const saved = fullPlan({
        route: "deposit",
        capital: "ready_130k",
      });
      savePlan(saved);

      const fragmentPlan = fullPlan({
        route: "property",
        capital: null,
        property: "none",
      });
      window.location.hash = `#p=${encodePlanFragment(fragmentPlan)}`;

      render(<StudioApp />);
      await screen.findByRole("heading", { name: /needs human review/i });

      fireEvent.click(screen.getByRole("button", { name: /other route/i }));
      expect(screen.getByTestId("scenario-toggle-preview")).toBeInTheDocument();

      const stored = JSON.parse(
        window.localStorage.getItem(PLAN_STORAGE_KEY) ?? "null",
      );
      expect(stored).toEqual(saved);
    });
  });

  describe("NavRow contrast fix (WCAG AA, 2026-08-24)", () => {
    // jsdom resolves neither `color-mix()` nor custom properties, so a
    // computed-color assertion here would be vacuous (verified instead on a
    // real Chromium render — see the commit body for the measured
    // before/after contrast numbers). These pin the RULE: the resting style
    // must not be the bare token that measured under the WCAG floor.
    it("primary CTA's resting background is not the bare --accent-funnel token (white-on-red measured 3.62:1, below the 4.5:1 floor for 16px/600 text)", () => {
      render(<StudioApp />);

      const continueBtn = screen.getByRole("button", { name: "Continue" });
      const styleAttr = continueBtn.getAttribute("style") ?? "";
      const bg = styleAttr.match(/background:\s*([^;]+)/)?.[1]?.trim();

      expect(bg).toBeDefined();
      expect(bg).not.toBe("var(--accent-funnel)");
    });

    it("Back button's resting border is not the bare --color-border-subtle token (measured ~1.2:1 against the card backdrop, below the 3.0:1 non-text UI floor)", () => {
      render(<StudioApp />);

      const backBtn = screen.getByRole("button", { name: "Back" });
      const styleAttr = backBtn.getAttribute("style") ?? "";
      const border = styleAttr.match(/border:\s*([^;]+)/)?.[1]?.trim();

      expect(border).toBeDefined();
      expect(border).not.toBe("1px solid var(--color-border-subtle)");
    });
  });
});

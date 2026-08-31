import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePricingData } from "@/hooks/usePricingData";
import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import {
  E33F_OFFSHORE_LIVE_PRICE_KEY,
  E33_LIVE_PRICE_KEY,
} from "@/lib/secondhome-studio/pricing-key";
import type { PlanState } from "@/lib/secondhome-studio/types";

import {
  ScenarioToggle,
  buildScenarioPreview,
  otherRoute,
} from "./ScenarioToggle";

vi.mock("@/hooks/usePricingData", () => ({
  usePricingData: vi.fn(),
}));

function basePlan(overrides: Partial<PlanState> = {}): PlanState {
  return { ...emptyPlan(), ...overrides };
}

describe("ScenarioToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(usePricingData).mockReturnValue({
      price: null,
      isLoading: false,
      isError: false,
    });
  });

  it("keeps the closed trigger neutral at rest and exposes accent only on interaction", () => {
    const { container } = render(
      <ScenarioToggle plan={basePlan({ route: "deposit" })} />,
    );
    const trigger = screen.getByRole("button", { name: /other route/i });
    const inlineStyle = trigger.getAttribute("style") ?? "";
    const css = container.querySelector("style")?.textContent ?? "";
    const restingRule = css.match(
      /\.bz-shs-scenario-toggle-trigger\s*\{([^}]*)\}/,
    )?.[1];

    expect(inlineStyle).not.toContain("--accent-funnel");
    expect(inlineStyle).not.toMatch(
      /(?:^|;)\s*(?:border|background|color)\s*:/,
    );
    expect(restingRule).toContain(
      "border: 1px solid var(--color-border-subtle)",
    );
    expect(restingRule).toContain("color: var(--text-secondary)");
    expect(restingRule).not.toContain("--accent-funnel");
    // The hover label reads the FLAT accent token. It used to be
    // color-mix(var(--accent-funnel) 70%, white), which was correct on the
    // retired navy ground — lightening moved it away from a dark backdrop.
    // On the day palette's carta that runs backwards: the mix lands ~#D8586D
    // and measures 3.07:1 against this rule's own 8% hover tint, below the
    // 4.5:1 this 16px/600 label needs, where flat #C8102E measures 4.77:1.
    // The mix is also a hue no token declares. Both are pinned centrally by
    // scripts/tests/test_merah_putih_day_contrast.py.
    const hoverRule = css.match(
      /\.bz-shs-scenario-toggle-trigger:is\(:hover, :focus-visible\)\s*\{([^}]*)\}/,
    )?.[1];
    // Judge the DECLARATIONS, not the rule's prose: the comment above this
    // very rule explains why we no longer mix toward white, so a naive
    // substring check on the raw body convicts its own documentation.
    const hoverDecls = (hoverRule ?? "").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(hoverDecls).toContain("border-color: var(--accent-funnel)");
    expect(hoverDecls).toContain("color: var(--accent-funnel)");
    expect(hoverDecls).toContain("text-decoration-line: underline");
    expect(hoverDecls).not.toContain("color-mix(in srgb, var(--accent-funnel)");
    expect(css).toMatch(
      /\.bz-shs-scenario-toggle-trigger:focus-visible\s*\{[^}]*outline:\s*3px solid var\(--accent-funnel\)[^}]*outline-offset:\s*3px/s,
    );
  });

  it("keeps its accessible name, decorative icon, and 44px touch target", () => {
    render(<ScenarioToggle plan={basePlan({ route: "deposit" })} />);
    const trigger = screen.getByRole("button", { name: /other route/i });
    const icon = trigger.querySelector("svg");

    expect(trigger).toBeInTheDocument();
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(Number.parseFloat(trigger.style.minHeight)).toBeGreaterThanOrEqual(
      44,
    );
  });

  it("opens the preview when the control is clicked and closes it with the back button", () => {
    render(<ScenarioToggle plan={basePlan({ route: "deposit" })} />);

    fireEvent.click(screen.getByRole("button", { name: /other route/i }));
    expect(screen.getByTestId("scenario-toggle-preview")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Back to your result/i }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Back to your result/i }),
    );
    expect(screen.queryByTestId("scenario-toggle-preview")).toBeNull();
    expect(
      screen.getByRole("button", { name: /other route/i }),
    ).toBeInTheDocument();
  });

  it("does not render when the plan has no route yet", () => {
    const { container } = render(<ScenarioToggle plan={basePlan()} />);
    expect(container.firstChild).toBeNull();
  });

  it("does not write to localStorage", () => {
    const plan = basePlan({
      route: "deposit",
      age: "under_55",
      capital: "ready_130k",
    });
    render(<ScenarioToggle plan={plan} />);

    fireEvent.click(screen.getByRole("button", { name: /other route/i }));
    expect(window.localStorage.length).toBe(0);
  });
});

describe("otherRoute", () => {
  it("swaps deposit and property, and treats unsure as property", () => {
    expect(otherRoute("deposit")).toBe("property");
    expect(otherRoute("property")).toBe("deposit");
    expect(otherRoute("unsure")).toBe("property");
  });
});

describe("buildScenarioPreview", () => {
  it("passes the copy through relevantPlan — capital is nulled when switching from deposit to property", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
      property: "owns_qualifying_strata",
    });
    const { previewPlan } = buildScenarioPreview(plan, "property");

    expect(previewPlan.capital).toBeNull();
    expect(previewPlan.property).toBe("owns_qualifying_strata");
    expect(previewPlan.route).toBe("property");
  });

  it("lists missing reachable questions for the other route", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    });
    const { missingQuestions } = buildScenarioPreview(plan, "property");

    expect(missingQuestions).toContain("property");
    expect(missingQuestions).not.toContain("capital");
  });

  it("shows the missing-answer copy for an unanswered property question", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    });
    render(<ScenarioToggle plan={plan} />);

    fireEvent.click(screen.getByRole("button", { name: /other route/i }));
    expect(
      screen.getByText(/what property position you hold/i),
    ).toBeInTheDocument();
  });

  it("preview price follows the preview product, not the real verdict product", () => {
    vi.mocked(usePricingData).mockImplementation((serviceKey) => ({
      price: serviceKey,
      isLoading: false,
      isError: false,
    }));

    const plan = basePlan({
      age: "60_plus",
      route: "property",
      property: "none",
      seniorFunding: "income_only_3k",
      location: "abroad",
    });
    render(<ScenarioToggle plan={plan} />);

    fireEvent.click(screen.getByRole("button", { name: /other route/i }));
    expect(screen.getByText(E33F_OFFSHORE_LIVE_PRICE_KEY)).toBeInTheDocument();
    expect(screen.queryByText(E33_LIVE_PRICE_KEY)).toBeNull();
  });
});

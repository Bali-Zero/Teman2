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

  it("renders the control label when closed", () => {
    render(<ScenarioToggle plan={basePlan({ route: "deposit" })} />);
    expect(
      screen.getByRole("button", { name: /other route/i }),
    ).toBeInTheDocument();
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

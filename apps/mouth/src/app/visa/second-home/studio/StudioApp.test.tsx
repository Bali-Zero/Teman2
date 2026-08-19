import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { usePricingData } from "@/hooks/usePricingData";
import {
  emptyPlan,
  encodePlanFragment,
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
 * question.
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

function clickButton(name: string) {
  fireEvent.click(screen.getByRole("button", { name }));
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
    window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
    render(<StudioApp />);

    expect(await screen.findByText(/0 of 10 prepared/)).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(10);
    fireEvent.click(checkboxes[0]);

    expect(await screen.findByText(/1 of 10 prepared/)).toBeInTheDocument();
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

  it("renders no price block when usePricingData abstains (null)", async () => {
    mockPrice(null);
    window.location.hash = `#p=${encodePlanFragment(fullPlan())}`;
    render(<StudioApp />);

    await screen.findByRole("heading", { name: /strong match/i });
    expect(screen.queryByText("Your all-inclusive figure")).toBeNull();
  });
});

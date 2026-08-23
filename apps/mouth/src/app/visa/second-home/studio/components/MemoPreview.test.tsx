import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PlanState } from "@/lib/secondhome-studio/types";

import { MemoPreview } from "./MemoPreview";

function basePlan(overrides: Partial<PlanState> = {}): PlanState {
  return {
    v: 1,
    age: null,
    route: null,
    capital: null,
    seniorFunding: null,
    property: null,
    family: { spouse: false, children: 0, parents: 0 },
    horizon: null,
    location: null,
    checklist: {},
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("MemoPreview", () => {
  beforeEach(() => {
    // Default jsdom has no matchMedia; the component treats that as the
    // mobile/interactive fallback. Tests that need desktop stub it below.
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: undefined,
    });
  });

  it("renders known rows with labels and resolved copy values", () => {
    render(
      <MemoPreview
        plan={basePlan({
          age: "60_plus",
          route: "deposit",
          capital: "ready_130k",
          seniorFunding: "income_only_3k",
          family: { spouse: true, children: 0, parents: 0 },
          horizon: "asap",
          location: "in_indonesia",
        })}
      />,
    );

    expect(screen.getByText("Age")).toBeInTheDocument();
    expect(screen.getByText("60 or over")).toBeInTheDocument();
    expect(screen.getByText("Route")).toBeInTheDocument();
    expect(screen.getByText("Bank deposit")).toBeInTheDocument();
    expect(screen.getByText("Capital")).toBeInTheDocument();
    expect(screen.getByText("USD 130,000 is ready")).toBeInTheDocument();
    expect(screen.getByText("Senior funding")).toBeInTheDocument();
    expect(screen.getByText("USD 3,000 monthly income only")).toBeInTheDocument();
    expect(screen.getByText("Family")).toBeInTheDocument();
    expect(screen.getByText("Spouse")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("As soon as possible")).toBeInTheDocument();
    expect(screen.getByText("Location")).toBeInTheDocument();
    expect(screen.getByText("In Indonesia")).toBeInTheDocument();
  });

  it("shows the property row for the property route and hides capital", () => {
    render(
      <MemoPreview
        plan={basePlan({
          age: "under_55",
          route: "property",
          property: "owns_qualifying_strata",
        })}
      />,
    );

    expect(screen.getByText("Property")).toBeInTheDocument();
    expect(screen.getByText("I own qualifying completed strata-title property")).toBeInTheDocument();
    expect(screen.queryByText("Capital")).toBeNull();
  });

  it("distinguishes unanswered rows with a placeholder state", () => {
    render(<MemoPreview plan={basePlan()} />);

    const ageRow = screen.getByTestId("memo-row-age");
    expect(ageRow).toHaveAttribute("data-known", "false");
    expect(ageRow.textContent).toContain("—");

    const valueCell = ageRow.querySelector("dd");
    expect(valueCell).toHaveStyle({
      fontWeight: "300",
      opacity: "0.55",
      fontStyle: "italic",
    });
  });

  it("marks rows as known when answered", () => {
    render(<MemoPreview plan={basePlan({ age: "under_55" })} />);
    const ageRow = screen.getByTestId("memo-row-age");
    expect(ageRow).toHaveAttribute("data-known", "true");

    const valueCell = ageRow.querySelector("dd");
    expect(valueCell).toHaveStyle({
      fontWeight: "500",
      opacity: "1",
      fontStyle: "normal",
    });
  });

  it("renders the growing left spine", () => {
    const { container } = render(
      <MemoPreview
        plan={basePlan({
          age: "under_55",
          route: "deposit",
          capital: "ready_130k",
          horizon: "asap",
          location: "in_indonesia",
        })}
      />,
    );
    const spine = container.querySelector(".bz-shs-memo-spine");
    expect(spine).toBeInTheDocument();
  });

  describe("desktop/mobile dual nature of the disclosure toggle", () => {
    it("makes the summary non-interactive and hides it from AT on desktop", () => {
      mockMatchMedia(true);
      render(<MemoPreview plan={basePlan({ age: "under_55" })} />);
      const summary = screen.getByText("Your plan so far").closest("summary");
      expect(summary).toHaveAttribute("tabIndex", "-1");
      expect(summary).toHaveAttribute("aria-hidden", "true");
    });

    it("keeps the summary interactive and exposed to AT on mobile", () => {
      mockMatchMedia(false);
      render(<MemoPreview plan={basePlan({ age: "under_55" })} />);
      const summary = screen.getByText("Your plan so far").closest("summary");
      expect(summary).not.toHaveAttribute("tabIndex");
      expect(summary).not.toHaveAttribute("aria-hidden");
    });

    it("falls back to the mobile/interactive default when matchMedia is absent", () => {
      render(<MemoPreview plan={basePlan({ age: "under_55" })} />);
      const summary = screen.getByText("Your plan so far").closest("summary");
      expect(summary).not.toHaveAttribute("tabIndex");
      expect(summary).not.toHaveAttribute("aria-hidden");
    });
  });

  describe("row entry animation", () => {
    it("animates a row that becomes known after the initial render", () => {
      const { rerender } = render(<MemoPreview plan={basePlan()} />);
      rerender(<MemoPreview plan={basePlan({ age: "under_55" })} />);

      const ageRow = screen.getByTestId("memo-row-age");
      expect(ageRow.classList.contains("bz-shs-memo-row-enter")).toBe(true);
    });

    it("does not animate rows that are already known when a value updates", () => {
      const { rerender } = render(
        <MemoPreview plan={basePlan({ age: "under_55" })} />,
      );
      rerender(<MemoPreview plan={basePlan({ age: "60_plus" })} />);

      const ageRow = screen.getByTestId("memo-row-age");
      expect(ageRow.classList.contains("bz-shs-memo-row-enter")).toBe(false);
    });

    it("does not animate any rows on the initial mount, even with a filled plan", () => {
      render(<MemoPreview plan={basePlan({ age: "under_55" })} />);
      const ageRow = screen.getByTestId("memo-row-age");
      expect(ageRow.classList.contains("bz-shs-memo-row-enter")).toBe(false);
    });
  });

  it("disables movement under prefers-reduced-motion: reduce", () => {
    const { container } = render(<MemoPreview plan={basePlan()} />);
    const styleTag = container.querySelector("style");
    expect(styleTag?.textContent).toMatch(
      /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/,
    );
    expect(styleTag?.textContent).toContain("animation: none !important");
    expect(styleTag?.textContent).toContain("transition: none !important");
  });
});

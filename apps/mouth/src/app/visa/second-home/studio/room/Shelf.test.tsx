import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import type { PlanState } from "@/lib/secondhome-studio/types";
import { DRAWERS, LIVE_ID_ARTICLE_HREF, Shelf } from "./Shelf";

vi.mock("@/hooks/usePricingData", () => ({
  usePricingData: vi.fn((key: string | null) => ({
    price: key === "E33E Second Home Senior (Extend)" ? null : `PRICE<${key}>`,
    isLoading: false,
    isError: false,
  })),
}));

vi.mock("@/i18n", () => ({
  useOptionalTranslation: () => ({ t: (key: string) => `t:${key}` }),
}));

function deepFreeze<T>(value: T): T {
  if (value && typeof value === "object") {
    Object.values(value as Record<string, unknown>).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

const plan: PlanState = deepFreeze({
  ...emptyPlan(),
  age: "under_55",
  route: "deposit",
  capital: "ready_130k",
});

const TITLES = ["Facts", "Checklist", "Tariff", "Compare", "Notes"];

function open(title: string) {
  fireEvent.click(
    screen.getByRole("button", { name: new RegExp(`^${title}`) }),
  );
  return screen.getByRole("dialog", { name: title });
}

describe("the shelf — five drawers of real material", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("shows the five drawer fronts as dialog triggers", () => {
    render(<Shelf plan={plan} verdict={null} />);
    expect(DRAWERS).toHaveLength(5);
    for (const title of TITLES) {
      const front = screen.getByRole("button", {
        name: new RegExp(`^${title}`),
      });
      expect(front).toHaveAttribute("aria-haspopup", "dialog");
      expect(front).toHaveAttribute("aria-expanded", "false");
    }
  });

  it("each drawer opens a labelled modal, focuses Close, and Close returns focus to its front", async () => {
    render(<Shelf plan={plan} verdict={null} />);
    for (const title of TITLES) {
      const front = screen.getByRole("button", {
        name: new RegExp(`^${title}`),
      });
      const dialog = open(title);
      expect(dialog).toHaveAttribute("aria-modal", "true");
      const close = within(dialog).getByRole("button", { name: "Close" });
      expect(close).toHaveFocus();
      fireEvent.click(close);
      expect(screen.queryByRole("dialog")).toBeNull();
      await waitFor(() => expect(front).toHaveFocus());
    }
  });

  it("Escape closes the open drawer", () => {
    render(<Shelf plan={plan} verdict={null} />);
    const dialog = open("Facts");
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opening every drawer never writes the plan (frozen plan, no storage write)", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    render(<Shelf plan={plan} verdict={null} />);
    for (const title of TITLES) {
      const dialog = open(title);
      fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    }
    expect(setItem).not.toHaveBeenCalled();
    expect(plan.checklist).toEqual(emptyPlan().checklist);
  });

  it("Facts: confirmed and open questions are both labelled; guarded facts never appear", () => {
    render(<Shelf plan={plan} verdict={null} />);
    const dialog = open("Facts");
    expect(within(dialog).getAllByText("Confirmed").length).toBeGreaterThan(0);
    expect(
      within(dialog).getAllByText("Not yet confirmed").length,
    ).toBeGreaterThan(0);
    for (const id of [
      "bsi_sharia_accepted",
      "split_deposit_accepted",
      "e33f_requirements",
      "age_55_59_ambiguity_e33e",
    ]) {
      expect(dialog.querySelector(`[data-fact-id="${id}"]`)).toBeNull();
    }
    expect(dialog.textContent).not.toMatch(/sharia|\bBSI\b|\bLPS\b/i);
  });

  it("Tariff: six rows, every figure from usePricingData, an honest gap when the list has none", () => {
    render(<Shelf plan={plan} verdict={null} />);
    const dialog = open("Tariff");
    const rows = within(dialog).getAllByRole("row");
    expect(rows).toHaveLength(7);
    expect(
      within(dialog).getByText("PRICE<E33 Second Home (5 Years)>"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Not on the price list right now"),
    ).toBeInTheDocument();
  });

  it("Compare: Indonesia, Malaysia and Portugal as columns, external sources linked", () => {
    render(<Shelf plan={plan} verdict={null} />);
    const dialog = open("Compare");
    const headers = within(dialog)
      .getAllByRole("columnheader")
      .map((h) => h.textContent ?? "");
    expect(headers.join(" ")).toMatch(/Indonesia/);
    expect(headers.join(" ")).toMatch(/Malaysia/);
    expect(headers.join(" ")).toMatch(/Portugal/);
    const links = within(dialog).getAllByRole("link");
    expect(links.length).toBeGreaterThan(0);
    for (const link of links)
      expect(link.getAttribute("href")).toMatch(/^https:\/\//);
  });

  it("Checklist: items sorted into applies / may apply, read-only (no checkbox)", () => {
    render(<Shelf plan={plan} verdict={null} />);
    const dialog = open("Checklist");
    expect(within(dialog).getByText("Applies to you")).toBeInTheDocument();
    expect(within(dialog).queryByRole("checkbox")).toBeNull();
  });

  it("Notes: the landing's FAQ keys and the live ID guide — never a noIndex E33 family", () => {
    render(<Shelf plan={plan} verdict={null} />);
    const dialog = open("Notes");
    expect(within(dialog).getByText("t:secondHome.faq.q1")).toBeInTheDocument();
    expect(within(dialog).getByText("t:secondHome.faq.q6")).toBeInTheDocument();
    const hrefs = within(dialog)
      .getAllByRole("link")
      .map((a) => a.getAttribute("href") ?? "");
    expect(hrefs).toContain(LIVE_ID_ARTICLE_HREF);
    for (const slug of [
      "indonesia-second-home-visa-2026-what-wealthy-expats-need-to-know-now",
      "indonesias-second-home-visa-kitas-e33-the-complete-2025-framework",
      "indonesias-second-home-visa-the-5-year-and-10-year-kitas-fully-decoded",
      "live-long-term-in-indonesia-second-home-golden-visa-pnb-immigration-law-firm",
    ]) {
      expect(hrefs.some((h) => h.includes(slug))).toBe(false);
    }
  });
});

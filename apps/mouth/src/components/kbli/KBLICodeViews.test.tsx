import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KBLICodeViews } from "./KBLICodeViews";
import type { KBLIPanelDetail } from "@/lib/kbli-panel-detail";

/**
 * What these pin: the filter is a verification filter and nothing else, the two
 * controls survive a reload through the URL, and the URL is REWRITTEN rather
 * than pushed — the panel's close gesture counts history entries, so a filter
 * that pushed one would strand the visitor inside the panel.
 */

function detail(over: Partial<KBLIPanelDetail> = {}): KBLIPanelDetail {
  return {
    code: "10111",
    titleEn: "Ruminant Slaughterhouse",
    titleId: "Rumah Potong Hewan",
    riskCategory: "Menengah Rendah",
    riskVerificationPending: false,
    pma: {
      status: "open",
      maxForeign: 100,
      capSpecial: false,
      capVerified: true,
      verdictVerified: true,
    },
    bali: { status: "open", blocked: false },
    transition: { status: "MATCH_LANGSUNG", from: [], note: null },
    provenanceState: "verified",
    ...over,
  } as KBLIPanelDetail;
}

const ITEMS = [
  detail({ code: "01111", provenanceState: "verified" }),
  detail({ code: "10111", provenanceState: "pending" }),
  detail({ code: "20111", provenanceState: "not_classifiable" }),
];

const cards = (
  <div>
    {ITEMS.map((i) => (
      <div key={i.code} data-kbli-verified={i.provenanceState === "verified"}>
        card-{i.code}
      </div>
    ))}
  </div>
);

function setUrl(search: string) {
  window.history.replaceState({}, "", `/kbli/sectors/A${search}`);
}

beforeEach(() => setUrl(""));

describe("KBLICodeViews", () => {
  it("defaults to All + cards, and counts every option", () => {
    render(<KBLICodeViews items={ITEMS} cards={cards} />);

    const group = screen.getByTestId("kbli-verified-filter");
    expect(within(group).getByRole("radio", { name: "All (3)" })).toBeChecked();
    expect(
      within(group).getByRole("radio", { name: "Verified (1)" }),
    ).toBeInTheDocument();
    expect(
      within(group).getByRole("radio", { name: "Unverified (2)" }),
    ).toBeInTheDocument();

    const views = screen.getByTestId("kbli-view-type");
    expect(within(views).getByRole("radio", { name: "Cards" })).toBeChecked();
    expect(screen.getByTestId("kbli-code-views-count")).toHaveTextContent(
      "3 of 3 codes",
    );
  });

  it("groups pending and not_classifiable together under Unverified", async () => {
    render(<KBLICodeViews items={ITEMS} cards={cards} />);
    await userEvent.click(
      screen.getByRole("radio", { name: "Unverified (2)" }),
    );

    await userEvent.click(screen.getByRole("radio", { name: "List" }));
    const list = screen.getByTestId("kbli-code-views-list");
    expect(within(list).getByText("10111")).toBeInTheDocument();
    expect(within(list).getByText("20111")).toBeInTheDocument();
    expect(within(list).queryByText("01111")).toBeNull();
  });

  it("writes both controls to the URL without adding a history entry", async () => {
    const push = vi.spyOn(window.history, "pushState");
    const before = window.history.length;
    render(<KBLICodeViews items={ITEMS} cards={cards} />);

    await userEvent.click(screen.getByRole("radio", { name: "Verified (1)" }));
    await userEvent.click(screen.getByRole("radio", { name: "Table" }));

    expect(window.location.search).toBe("?verified=verified&view=table");
    expect(push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(before);
    push.mockRestore();
  });

  it("restores both controls from the URL on mount", async () => {
    setUrl("?verified=verified&view=table");
    render(<KBLICodeViews items={ITEMS} cards={cards} />);

    expect(screen.getByRole("radio", { name: "Verified (1)" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Table" })).toBeChecked();
    const table = screen.getByTestId("kbli-code-views-table");
    expect(within(table).getByText("01111")).toBeInTheDocument();
    expect(within(table).queryByText("10111")).toBeNull();
  });

  it("falls back to the full list when the URL names a filter that does not exist", () => {
    setUrl("?verified=maybe&view=timeline");
    render(<KBLICodeViews items={ITEMS} cards={cards} />);

    expect(screen.getByRole("radio", { name: "All (3)" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Cards" })).toBeChecked();
  });

  it("keeps the cards markup mounted and untouched, filtering it by data attribute", async () => {
    render(<KBLICodeViews items={ITEMS} cards={cards} />);
    await userEvent.click(screen.getByRole("radio", { name: "Verified (1)" }));

    const container = screen.getByTestId("kbli-code-views-cards");
    expect(container).toHaveAttribute("data-kbli-verified-filter", "verified");
    // Still in the DOM — the hiding is the CSS rule's job, not React's.
    expect(within(container).getByText("card-10111")).toBeInTheDocument();
  });

  it("shows an empty state, and no table, when nothing matches", async () => {
    render(
      <KBLICodeViews
        items={[detail({ code: "10111", provenanceState: "pending" })]}
        cards={cards}
      />,
    );
    await userEvent.click(screen.getByRole("radio", { name: "Verified (0)" }));

    expect(screen.getByTestId("kbli-code-views-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("kbli-code-views-cards")).toBeNull();
    expect(screen.getByTestId("kbli-code-views-count")).toHaveTextContent(
      "0 of 1 code",
    );
  });

  it("is a radio group that arrow keys move through, with one stop in the tab order", async () => {
    render(<KBLICodeViews items={ITEMS} cards={cards} />);
    const group = screen.getByTestId("kbli-verified-filter");
    expect(group).toHaveAttribute("role", "radiogroup");

    const all = within(group).getByRole("radio", { name: "All (3)" });
    all.focus();
    expect(all).toHaveAttribute("tabindex", "0");
    expect(
      within(group).getByRole("radio", { name: "Verified (1)" }),
    ).toHaveAttribute("tabindex", "-1");

    await userEvent.keyboard("{ArrowRight}");
    expect(
      within(group).getByRole("radio", { name: "Verified (1)" }),
    ).toBeChecked();
    expect(window.location.search).toBe("?verified=verified");

    await userEvent.keyboard("{End}");
    expect(
      within(group).getByRole("radio", { name: "Unverified (2)" }),
    ).toBeChecked();
  });

  it("shows the verified badge only on verified rows", async () => {
    render(<KBLICodeViews items={ITEMS} cards={cards} />);
    await userEvent.click(screen.getByRole("radio", { name: "Table" }));

    const table = screen.getByTestId("kbli-code-views-table");
    expect(within(table).getAllByText(/OSS-verified/)).toHaveLength(1);
    expect(within(table).getAllByText("Unverified")).toHaveLength(2);
  });
});

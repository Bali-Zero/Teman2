import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { KBLISearch } from "./KBLISearch";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const search = vi.fn();
vi.mock("@/lib/api/kbli.api", () => ({
  kbliApi: { search: (q: string) => search(q) },
  apiPmaStatusLabel: () => "Open",
  isApiPmaVerdictVerified: () => true,
}));
vi.mock("@/lib/analytics", () => ({ trackKBLISearch: vi.fn() }));

const RESULTS = [
  {
    code: "56101",
    title: "Restoran",
    description: "Restaurants",
    risk_category: "MR",
  },
  {
    code: "55130",
    title: "Villa",
    description: "Villas",
    risk_category: "MT",
  },
];

/** Type a term and wait for the dropdown the debounced search opens. */
async function openDropdown() {
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "rest" } });
  await screen.findAllByRole("option", {}, { timeout: 2000 });
  return input;
}

describe("KBLISearch combobox semantics", () => {
  beforeEach(() => {
    push.mockReset();
    search.mockReset();
    search.mockResolvedValue(RESULTS);
  });

  it("exposes the input as a collapsed combobox before any search", () => {
    render(<KBLISearch />);
    const input = screen.getByRole("combobox");

    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(input).toHaveAttribute("aria-autocomplete", "list");
    expect(input).toHaveAttribute("aria-controls");
    expect(input).not.toHaveAttribute("aria-activedescendant");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("expands into a listbox of options, wired to the input by id", async () => {
    render(<KBLISearch />);
    const input = await openDropdown();

    const listbox = screen.getByRole("listbox");
    expect(input).toHaveAttribute("aria-expanded", "true");
    expect(input.getAttribute("aria-controls")).toBe(listbox.id);
    expect(screen.getAllByRole("option")).toHaveLength(RESULTS.length);
  });

  // The whole point of the PR: arrow keys already moved the highlight, but
  // nothing announced it. aria-activedescendant is what makes it perceivable.
  it("points aria-activedescendant at the row the arrow keys highlight", async () => {
    render(<KBLISearch />);
    const input = await openDropdown();
    const [first, second] = screen.getAllByRole("option");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    await waitFor(() =>
      expect(input).toHaveAttribute("aria-activedescendant", first.id),
    );
    expect(first).toHaveAttribute("aria-selected", "true");
    expect(second).toHaveAttribute("aria-selected", "false");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    await waitFor(() =>
      expect(input).toHaveAttribute("aria-activedescendant", second.id),
    );
    expect(first).toHaveAttribute("aria-selected", "false");
    expect(second).toHaveAttribute("aria-selected", "true");
  });

  it("keeps focus on the input while the highlight moves", async () => {
    render(<KBLISearch />);
    const input = await openDropdown();
    input.focus();

    fireEvent.keyDown(input, { key: "ArrowDown" });
    await waitFor(() => expect(input).toHaveAttribute("aria-activedescendant"));
    expect(document.activeElement).toBe(input);
  });

  it("announces the result count in a polite live region", async () => {
    render(<KBLISearch />);
    await openDropdown();

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(`${RESULTS.length} KBLI codes found`);
  });

  // Two instances on one page (hero + inline) must not share a listbox id, or
  // every aria reference on the second one resolves to the first one's rows.
  it("gives each rendered instance its own listbox id", () => {
    render(
      <>
        <KBLISearch />
        <KBLISearch />
      </>,
    );
    const [a, b] = screen.getAllByRole("combobox");
    expect(a.getAttribute("aria-controls")).not.toBe(
      b.getAttribute("aria-controls"),
    );
  });
});

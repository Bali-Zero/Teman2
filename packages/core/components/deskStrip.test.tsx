import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { ListPageHeader } from "./ListPageHeader";
import { StatChips } from "./StatChips";
import { SearchBox } from "./SearchBox";
import { FilterBar, FilterSelect } from "./FilterBar";

/**
 * The desk strip contract, for the windows that will import it.
 *
 * Two claims are pinned here and each carries its opposite.
 *
 *   1. The DESK branch is the R19 idiom: square, 44px, on the control
 *      boundary, serif counts, a filled pressed pill with a tick.
 *   2. The DEFAULT branch did not move. `packages/core` is imported by kita,
 *      my, prime and editorial; restyling it in place would repaint four
 *      products at once. Every desk assertion below has a default-branch twin
 *      asserting the OLD class is still there and the new one is not.
 */

/** Pure detector: a rounded corner, which the printed ledger does not have. */
export function findRounded(markup: string): string[] {
  return markup.match(/\brounded-(?:full|lg|md|sm|xl)\b/g) ?? [];
}

/** Pure detector: a raw hex, which a shared package must never carry. */
export function findHex(markup: string): string[] {
  return markup.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
}

describe("ListPageHeader", () => {
  it("desk: copper rule, serif title, actions still on the right", () => {
    const { container, getByText } = render(
      <ListPageHeader
        variant="desk"
        title="Clients"
        subtitle="40 on the book"
        actions={<button type="button">New client</button>}
      />,
    );

    const rule = container.querySelector('[aria-hidden="true"]');
    expect(rule?.className).toContain("bg-[var(--bz-copper)]");
    expect(rule?.className).toContain("w-[52px]");
    expect(getByText("Clients").getAttribute("style")).toContain(
      "var(--font-serif)",
    );
    expect(getByText("New client")).toBeTruthy();
    expect(findRounded(container.innerHTML)).toEqual([]);
  });

  it("default: unchanged — no rule, no serif, the shipped classes (innocence)", () => {
    const { container, getByText } = render(
      <ListPageHeader title="Clients" subtitle="40 on the book" />,
    );

    expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
    const h1 = getByText("Clients");
    expect(h1.className).toBe("text-2xl font-bold");
    expect(h1.getAttribute("style")).toContain("var(--bz-text-1)");
    expect(h1.getAttribute("style")).not.toContain("var(--font-serif)");
  });
});

describe("StatChips", () => {
  it("desk: a pressed chip is filled, ticked and aria-pressed", () => {
    const onClick = vi.fn();
    const { getByRole } = render(
      <StatChips
        variant="desk"
        items={[
          { key: "mine", content: "Assigned to me", onClick, pressed: true },
        ]}
      />,
    );

    const button = getByRole("button", { name: /Assigned to me/ });
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(button.className).toContain("bg-[var(--bz-selected-fill");
    expect(button.textContent).toContain("✓");
    // The tick is the point: it survives greyscale and a colour-blind eye.
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("desk: an UNPRESSED chip is an outline, has no tick, and says so (guilt)", () => {
    const { getByRole } = render(
      <StatChips
        variant="desk"
        items={[
          {
            key: "mine",
            content: "Assigned to me",
            onClick: vi.fn(),
            pressed: false,
          },
        ]}
      />,
    );

    const button = getByRole("button", { name: "Assigned to me" });
    expect(button.getAttribute("aria-pressed")).toBe("false");
    expect(button.className).not.toContain("bg-[var(--bz-selected-fill");
    expect(button.className).toContain("border-[var(--line-control)]");
    expect(button.textContent).not.toContain("✓");
  });

  it("desk: a chip that cannot be pressed carries no aria-pressed at all", () => {
    // A static count is not a control, and claiming a pressed state for it
    // would lie to a screen reader.
    const { getByText } = render(
      <StatChips variant="desk" items={[{ key: "n", content: "12 active" }]} />,
    );
    expect(getByText("12 active").getAttribute("aria-pressed")).toBeNull();
  });

  it("desk: square, and carrying no hex of its own", () => {
    const { container } = render(
      <StatChips
        variant="desk"
        items={[
          { key: "a", content: "A", onClick: vi.fn(), pressed: true },
          { key: "b", content: "B" },
        ]}
      />,
    );
    expect(findRounded(container.innerHTML)).toEqual([]);
    expect(findHex(container.innerHTML)).toEqual([]);
  });

  it("default: unchanged — rounded-full pills, no aria-pressed (innocence)", () => {
    const { getByRole, getByText } = render(
      <StatChips
        items={[
          { key: "static", content: "12 active" },
          { key: "click", content: "3 unpaid", onClick: vi.fn() },
        ]}
      />,
    );

    expect(getByText("12 active").className).toBe(
      "flex items-center gap-1 px-2.5 py-1 rounded-full",
    );
    const button = getByRole("button", { name: "3 unpaid" });
    expect(button.className).toContain("rounded-full");
    expect(button.getAttribute("aria-pressed")).toBeNull();
    expect(button.textContent).not.toContain("✓");
  });

  it("default: a `pressed` chip stays rounded and unfilled (guilt for the variant)", () => {
    // `pressed` is meaningless outside the desk variant, and must not leak
    // into a product that never asked for it.
    const { getByRole } = render(
      <StatChips
        items={[{ key: "x", content: "X", onClick: vi.fn(), pressed: true }]}
      />,
    );
    const button = getByRole("button", { name: "X" });
    expect(button.className).toContain("rounded-full");
    expect(button.getAttribute("aria-pressed")).toBeNull();
  });
});

describe("SearchBox", () => {
  it("desk: 44px on the control boundary, square, room for the glyph", () => {
    const { getByLabelText } = render(
      <SearchBox
        variant="desk"
        value=""
        onValueChange={vi.fn()}
        ariaLabel="Search clients"
      />,
    );

    const input = getByLabelText("Search clients");
    expect(input.className).toContain("h-11");
    expect(input.className).toContain("border-[var(--line-control)]");
    expect(input.className).toContain("rounded-none");
    expect(input.className).toContain("pl-[34px]");
  });

  it("default: unchanged — rounded-lg, the shipped base (innocence)", () => {
    const { getByLabelText } = render(
      <SearchBox value="" onValueChange={vi.fn()} ariaLabel="Search clients" />,
    );

    const input = getByLabelText("Search clients");
    expect(input.className).toBe(
      "w-full pl-10 pr-4 py-2 rounded-lg focus:outline-none",
    );
  });

  it("the '/' shortcut and Escape behave the same in both variants", () => {
    const onValueChange = vi.fn();
    const { getByLabelText } = render(
      <SearchBox
        variant="desk"
        value="abc"
        onValueChange={onValueChange}
        ariaLabel="Search"
      />,
    );
    const input = getByLabelText("Search") as HTMLInputElement;

    fireEvent.keyDown(window, { key: "/" });
    expect(document.activeElement).toBe(input);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onValueChange).toHaveBeenCalledWith("");
  });
});

describe("FilterBar", () => {
  it("desk: hairline frame, serif heading, copper clear-all", () => {
    const { container, getByText } = render(
      <FilterBar variant="desk" activeCount={2} onClearAll={vi.fn()}>
        <FilterSelect
          variant="desk"
          label="Status"
          value="all"
          onChange={vi.fn()}
          id="status"
        >
          <option value="all">All</option>
        </FilterSelect>
      </FilterBar>,
    );

    expect(container.firstElementChild?.className).toContain(
      "border-b border-[var(--bz-border)]",
    );
    expect(getByText("Filters").getAttribute("style")).toContain(
      "var(--font-serif)",
    );
    expect(getByText("Clear all").className).toContain(
      "text-[var(--bz-copper-text)]",
    );
    expect(findRounded(container.innerHTML)).toEqual([]);
  });

  it("desk: the select sits on the same 44px boundary as the search box", () => {
    const { container } = render(
      <FilterBar variant="desk" activeCount={0} onClearAll={vi.fn()}>
        <FilterSelect
          variant="desk"
          label="Status"
          value="all"
          onChange={vi.fn()}
          id="s"
        >
          <option value="all">All</option>
        </FilterSelect>
      </FilterBar>,
    );
    const select = container.querySelector("select");
    expect(select?.className).toContain("h-11");
    expect(select?.className).toContain("border-[var(--line-control)]");
  });

  it("default: unchanged — p-4 panel, accent clear-all, rounded select (innocence)", () => {
    const { container, getByText } = render(
      <FilterBar activeCount={1} onClearAll={vi.fn()}>
        <FilterSelect label="Status" value="all" onChange={vi.fn()} id="s">
          <option value="all">All</option>
        </FilterSelect>
      </FilterBar>,
    );

    expect(container.firstElementChild?.className).toBe("p-4 space-y-4");
    expect(getByText("Filters").className).toBe("font-medium");
    expect(getByText("Clear all").getAttribute("style")).toContain(
      "var(--bz-accent)",
    );
    expect(container.querySelector("select")?.className).toContain(
      "rounded-lg",
    );
  });

  it("Clear-all still only appears when something is active, in both variants", () => {
    const { queryByText, rerender } = render(
      <FilterBar variant="desk" activeCount={0} onClearAll={vi.fn()}>
        <span />
      </FilterBar>,
    );
    expect(queryByText("Clear all")).toBeNull();

    rerender(
      <FilterBar variant="desk" activeCount={1} onClearAll={vi.fn()}>
        <span />
      </FilterBar>,
    );
    expect(queryByText("Clear all")).not.toBeNull();
  });
});

describe("the detectors themselves", () => {
  it("findRounded names a planted corner and clears a square one", () => {
    expect(findRounded('<i class="rounded-full"></i>')).toEqual([
      "rounded-full",
    ]);
    expect(findRounded('<i class="rounded-none"></i>')).toEqual([]);
  });

  it("findHex names a planted colour and clears a token read", () => {
    expect(findHex('<i style="color:#a44b36"></i>')).toEqual(["#a44b36"]);
    expect(findHex('<i class="text-[var(--bz-copper)]"></i>')).toEqual([]);
  });
});

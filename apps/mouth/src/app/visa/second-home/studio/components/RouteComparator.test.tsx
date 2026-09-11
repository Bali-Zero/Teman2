import { describe, expect, it } from "vitest";
import { render, within } from "@testing-library/react";
import { RouteComparator } from "./RouteComparator";

function relativeLuminance(hex: string): number {
  const channels = hex
    .slice(1)
    .match(/../g)
    ?.map((channel) => Number.parseInt(channel, 16) / 255);

  if (!channels || channels.length !== 3) {
    throw new Error(`Invalid hex colour: ${hex}`);
  }

  const [red, green, blue] = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(foreground: string, background: string): number {
  const luminances = [
    relativeLuminance(foreground),
    relativeLuminance(background),
  ].sort((a, b) => b - a);

  return (luminances[0] + 0.05) / (luminances[1] + 0.05);
}

describe("RouteComparator", () => {
  it("keeps the wide comparison as a semantic table with three named routes", () => {
    const { container } = render(<RouteComparator />);
    const tableView = container.querySelector<HTMLElement>(
      '[data-comparison-view="table"]',
    );

    expect(tableView).not.toBeNull();
    const table = within(tableView as HTMLElement);
    expect(
      table.getByRole("table", { name: "Second Home route comparison" }),
    ).toBeInTheDocument();
    expect(table.getByText("Deposit route")).toBeInTheDocument();
    expect(table.getByText("Property route")).toBeInTheDocument();
    expect(table.getByText("Senior route (55+)")).toBeInTheDocument();
    expect(table.getAllByRole("columnheader")).toHaveLength(4);
    expect(table.getAllByRole("rowheader")).toHaveLength(4);
  });

  it("gives each route a different hidden icon and preserves highlight", () => {
    const { container } = render(<RouteComparator highlight />);
    const icons = container.querySelectorAll(
      '[data-comparison-view="table"] .bz-shs-route-icon > svg[aria-hidden="true"]',
    );

    expect(icons).toHaveLength(3);
    expect(
      new Set(Array.from(icons, (icon) => icon.getAttribute("class"))).size,
    ).toBe(3);
    expect(container.querySelector("section")).toHaveAttribute(
      "data-highlighted",
      "true",
    );
    expect(container.querySelector("section")?.getAttribute("style")).toContain(
      "border: 2px solid var(--accent-funnel)",
    );
  });

  it("keeps every route fact and explicit mobile label/value pair", () => {
    const { container } = render(<RouteComparator />);
    const cards = Array.from(
      container.querySelectorAll<HTMLElement>("[data-route-card]"),
    );

    expect(cards).toHaveLength(3);
    for (const card of cards) {
      expect(card.querySelectorAll("dt")).toHaveLength(4);
      expect(card.querySelectorAll("dd")).toHaveLength(4);
    }

    expect(cards[0]).toHaveTextContent(
      "USD 130,000 held on deposit, in your own name",
    );
    expect(cards[0]).toHaveTextContent(
      "A deposit at a state-owned (BUMN) Indonesian bank",
    );
    expect(cards[1]).toHaveTextContent(
      "USD 1,000,000 completed strata-title property",
    );
    expect(cards[1]).toHaveTextContent(
      "Only a completed strata-title unit — villas, land, leasehold, and off-plan do not qualify",
    );
    expect(cards[1]).toHaveTextContent(
      "Pending our property validation standard",
    );
    expect(cards[2]).toHaveTextContent(
      "USD 50,000 deposit plus USD 3,000/month income, or USD 3,000/month income only",
    );
    expect(cards[2]).toHaveTextContent(
      "Age 55 or older, with a matching funding pattern",
    );
  });

  it("has no horizontal scroll container and switches to cards at the mobile breakpoint", () => {
    const { container } = render(<RouteComparator />);
    const css = container.querySelector("style")?.textContent ?? "";
    const sectionStyle =
      container.querySelector("section")?.getAttribute("style") ?? "";

    expect(css).not.toMatch(/overflow(?:-x)?\s*:\s*(?:auto|scroll)/i);
    expect(sectionStyle).toContain("min-width: 0px");
    expect(sectionStyle).toContain("width: 100%");
    expect(sectionStyle).toContain("max-width: 100%");
    expect(sectionStyle).toContain("box-sizing: border-box");
    expect(css).toMatch(/@media \(max-width: 760px\)/);
    expect(css).toMatch(/\.bz-shs-route-table-view\s*{\s*display:\s*none;/);
    expect(css).toMatch(/\.bz-shs-route-cards\s*{\s*display:\s*grid;/);
    expect(css).toMatch(
      /grid-template-columns:\s*minmax\(0, 1fr\);[\s\S]*?\.bz-shs-route-card\s*{[\s\S]*?min-width:\s*0;/,
    );
  });

  it("route headings (table + mobile cards) use Inter 600, not Cormorant, at 1rem (16px) — below the R4 §3 24px display floor", () => {
    const { container } = render(<RouteComparator />);
    const css = container.querySelector("style")?.textContent ?? "";
    const rule = css.match(/\.bz-shs-route-heading\s*{([^}]+)}/)?.[1] ?? "";
    const fontFamily = rule.match(/font-family:\s*([^;]+);/)?.[1]?.trim();
    const fontSize = rule.match(/font-size:\s*([^;]+);/)?.[1]?.trim();
    const fontWeight = rule.match(/font-weight:\s*([^;]+);/)?.[1]?.trim();

    expect(fontFamily).toBe(
      "var(--font-sans, ui-sans-serif, system-ui, sans-serif)",
    );
    expect(fontSize).toBe("1rem");
    expect(fontWeight).toBe("600");

    // The class must actually be live on both the table th and the mobile
    // card h3, not just declared in an unused stylesheet rule.
    const headings = container.querySelectorAll(".bz-shs-route-heading");
    expect(headings.length).toBeGreaterThanOrEqual(6); // 3 table + 3 cards
  });

  it("keeps text AA and identity marks perceivable on every route tint", () => {
    const { container } = render(<RouteComparator />);
    const css = container.querySelector("style")?.textContent ?? "";
    const copy = css.match(/--route-copy:\s*(#[0-9a-f]{6})/i)?.[1];
    const label = css.match(/--route-label:\s*(#[0-9a-f]{6})/i)?.[1];
    const tints = Array.from(
      css.matchAll(/--route-tint:\s*(#[0-9a-f]{6})/gi),
      (match) => match[1],
    );
    const accents = Array.from(
      css.matchAll(/--route-accent:\s*(#[0-9a-f]{6})/gi),
      (match) => match[1],
    );

    if (!copy || !label) {
      throw new Error("Route text colours are missing");
    }
    expect(tints).toHaveLength(3);
    expect(accents).toHaveLength(3);
    for (const tint of tints) {
      expect(contrastRatio(copy, tint)).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(label, tint)).toBeGreaterThanOrEqual(4.5);
    }
    for (const [index, accent] of accents.entries()) {
      expect(contrastRatio(accent, tints[index])).toBeGreaterThanOrEqual(3);
    }
    expect(contrastRatio("#704116", "#fff7e8")).toBeGreaterThanOrEqual(4.5);
  });
});

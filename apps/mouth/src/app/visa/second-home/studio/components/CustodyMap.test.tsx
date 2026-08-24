import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { COPY } from "@/lib/secondhome-studio/copy";

import { CustodyMap } from "./CustodyMap";

const custodyStrings = [
  COPY.custody.eyebrow,
  COPY.custody.intro,
  ...Object.values(COPY.custody.steps).flatMap(({ title, body }) => [
    title,
    body,
  ]),
  COPY.custody.disclaimer,
];

describe("CustodyMap", () => {
  it("renders three keyboard-reachable custody nodes", () => {
    render(<CustodyMap />);

    const nodes = screen.getAllByRole("button");
    expect(nodes).toHaveLength(3);
    expect(nodes.map((node) => node.textContent)).toEqual(
      Object.values(COPY.custody.steps).map(({ title }) => title),
    );
    nodes.forEach((node) =>
      expect(node).toHaveAttribute("aria-expanded", "false"),
    );
  });

  it("expands and closes a node detail", () => {
    render(<CustodyMap />);

    const firstNode = screen.getByRole("button", {
      name: COPY.custody.steps.step1.title,
    });
    fireEvent.click(firstNode);

    expect(firstNode).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(COPY.custody.steps.step1.body)).toBeInTheDocument();

    fireEvent.click(firstNode);
    expect(firstNode).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(COPY.custody.steps.step1.body)).not.toBeVisible();
  });

  it("provides a text equivalent for the visual flow", () => {
    render(<CustodyMap />);

    expect(
      screen.getByRole("group", { name: COPY.custody.eyebrow }),
    ).toHaveAccessibleDescription(COPY.custody.intro);
    expect(screen.getByRole("list")).toBeInTheDocument();
  });

  it("prints every node body and removes the interactive chevrons", () => {
    const { container } = render(<CustodyMap />);
    const css = Array.from(container.querySelectorAll("style"))
      .map((style) => style.textContent ?? "")
      .join("\n");

    expect(css).toMatch(
      /@media print\s*{[\s\S]*?\.custody-node > p\[data-collapsed="true"\]\s*{[\s\S]*?display: block !important;/,
    );
    expect(css).toMatch(
      /@media print\s*{[\s\S]*?\.custody-chevron\s*{[\s\S]*?display: none !important;/,
    );
  });

  // 2026-08-24 print-layout fix: at A4 print width the 3-column step grid
  // squeezed each card to ~55px, wrapping headings one word per line and
  // clipping "Use the bank evidence for your application" mid-word. Fixed
  // by stacking to one column in `@media print`.
  //
  // jsdom does not evaluate `@media` at all (no layout engine, no paginator)
  // so this — like the "prints every node body" test above it — can only
  // regex-match the emitted CSS source text. That proves the rule exists
  // and targets the right selectors; it does NOT prove the browser actually
  // computes a single-column, non-clipped layout when printing. The real
  // proof for that is the rendered-PDF check done by hand for this change
  // (before/after screenshots) — this test exists to catch a regression
  // that deletes or renames the rule, not to catch a regression in what it
  // visually produces.
  it("stacks the money-path steps to one column and hides arrows in print (source-text only, see comment)", () => {
    const { container } = render(<CustodyMap />);
    const css = Array.from(container.querySelectorAll("style"))
      .map((style) => style.textContent ?? "")
      .join("\n");

    expect(css).toMatch(
      /@media print\s*{[\s\S]*?\.custody-layout,\s*\n\s*\.custody-flow\s*{[\s\S]*?grid-template-columns: minmax\(0, 1fr\) !important;/,
    );
    expect(css).toMatch(
      /@media print\s*{[\s\S]*?\.custody-arrow\s*{[\s\S]*?display: none !important;/,
    );
    expect(css).toMatch(
      /@media print\s*{[\s\S]*?\.custody-outside::before\s*{[\s\S]*?display: none !important;/,
    );
  });

  it("renders only user-visible strings sourced from copy.ts", () => {
    const { container } = render(<CustodyMap />);
    const assertRenderedTextComesFromCopy = () => {
      const textNodes: string[] = [];
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const parent = walker.currentNode.parentElement;
        if (parent?.closest('style, [data-collapsed="true"]')) continue;
        const value = walker.currentNode.textContent?.trim();
        if (value) textNodes.push(value);
      }

      expect(textNodes).not.toHaveLength(0);
      textNodes.forEach((value) => expect(custodyStrings).toContain(value));
    };

    assertRenderedTextComesFromCopy();
    Object.values(COPY.custody.steps).forEach(({ title, body }) => {
      fireEvent.click(screen.getByRole("button", { name: title }));
      expect(screen.getByText(body)).toBeVisible();
      assertRenderedTextComesFromCopy();
    });
  });
});

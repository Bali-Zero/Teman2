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

  it("renders only user-visible strings sourced from copy.ts", () => {
    const { container } = render(<CustodyMap />);
    const assertRenderedTextComesFromCopy = () => {
      const textNodes: string[] = [];
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const parent = walker.currentNode.parentElement;
        if (parent?.closest("style, [hidden]")) continue;
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

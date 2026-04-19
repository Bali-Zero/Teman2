import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NavShell } from "./NavShell";

const ITEMS = [
  { label: "Services", href: "#s" },
  { label: "Visa Oracle", href: "#v" },
];

describe("NavShell", () => {
  it("renders logo, items, and actions", () => {
    const { container, getByText } = render(
      <NavShell
        logo={<span data-testid="logo">L</span>}
        items={ITEMS}
        actions={<button data-testid="cta">Go</button>}
      />,
    );
    expect(container.querySelector("[data-testid='logo']")).toBeTruthy();
    expect(getByText("Services")).toBeTruthy();
    expect(getByText("Visa Oracle")).toBeTruthy();
    expect(container.querySelector("[data-testid='cta']")).toBeTruthy();
  });

  it("mounts slotBefore and slotAfter when provided", () => {
    const { getByTestId } = render(
      <NavShell
        logo={<span />}
        items={ITEMS}
        actions={<span />}
        slotBefore={<input data-testid="search" />}
        slotAfter={<select data-testid="lang" />}
      />,
    );
    expect(getByTestId("search")).toBeTruthy();
    expect(getByTestId("lang")).toBeTruthy();
  });

  it("children escape hatch overrides items rendering", () => {
    const { container, queryByText } = render(
      <NavShell logo={<span />} items={ITEMS} actions={<span />}>
        <div data-testid="custom">custom center</div>
      </NavShell>,
    );
    expect(container.querySelector("[data-testid='custom']")).toBeTruthy();
    // items should not render when children is provided
    expect(queryByText("Services")).toBeNull();
  });

  it("reads only semantic tokens (no inline hex)", () => {
    const { container } = render(
      <NavShell logo={<span />} items={ITEMS} actions={<span />} />,
    );
    const html = container.innerHTML;
    // Forbid inline hex in the component's rendered output
    expect(html.match(/#[0-9a-fA-F]{6}/)).toBeNull();
  });
});

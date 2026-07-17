import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TransitionBadge } from "./TransitionBadge";

describe("TransitionBadge — dark-theme tokens", () => {
  it("renders a labeled pill styled from a --kbli-* token, never a light-mode class", () => {
    const { container } = render(<TransitionBadge status="MATCH_LANGSUNG" />);
    expect(screen.getByText("Direct Match")).toBeDefined();
    const span = container.querySelector("span")!;
    // color comes from the theme token, not a hardcoded light-mode class
    expect(span.style.color).toContain("--kbli-pma-open");
    expect(span.getAttribute("class") ?? "").not.toMatch(
      /bg-(green|blue|amber|purple)-\d/,
    );
  });

  it("innocence: empty status renders nothing", () => {
    const { container } = render(<TransitionBadge status="" />);
    expect(container.firstChild).toBeNull();
  });
});

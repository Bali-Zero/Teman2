import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { FactBadge } from "./FactBadge";

describe("FactBadge", () => {
  it("renders children", () => {
    const { getByText } = render(<FactBadge>KBLI 47911</FactBadge>);
    expect(getByText("KBLI 47911")).toBeTruthy();
  });

  it("carries the fact-badge class and data-role hook", () => {
    const { container } = render(<FactBadge>47911</FactBadge>);
    const el = container.querySelector("[data-role='fact-badge']");
    expect(el).toBeTruthy();
    expect(el?.className).toContain("fact-badge");
  });

  it("reads the fact-badge semantic tokens", () => {
    const { container } = render(<FactBadge>47911</FactBadge>);
    const el = container.querySelector(
      "[data-role='fact-badge']",
    ) as HTMLElement;
    expect(el.style.background).toBe("var(--fact-badge-bg)");
    expect(el.style.color).toBe("var(--fact-badge-fg)");
    expect(el.style.borderRadius).toBe("var(--fact-badge-radius)");
    expect(el.style.fontFamily).toBe("var(--font-mono, monospace)");
  });

  it("merges className after the base class", () => {
    const { container } = render(<FactBadge className="ml-2">47911</FactBadge>);
    const el = container.querySelector("[data-role='fact-badge']");
    expect(el?.className).toBe("fact-badge ml-2");
  });

  it("passes title through for the source citation", () => {
    const { container } = render(
      <FactBadge title="UU 25/2007">47911</FactBadge>,
    );
    const el = container.querySelector("[data-role='fact-badge']");
    expect(el?.getAttribute("title")).toBe("UU 25/2007");
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Verdict, VerdictBand } from "@/lib/secondhome-studio/types";
import { VerdictPanel } from "./VerdictPanel";

const baseVerdict = (band: VerdictBand): Verdict => ({
  band,
  product: band === "not_eligible" || band === "edge_case" ? null : "E33",
  reasons: [],
  humanReviewNote: null,
});

/** Read the inline border style written by the component. */
function getPanelBorder(section: HTMLElement): {
  width: number;
  color: string;
} {
  const border = section.style.border;
  const match = border.match(/^(\d+)px solid (.+)$/);
  if (!match) {
    throw new Error(`Unexpected border style: ${border}`);
  }
  return { width: Number(match[1]), color: match[2] };
}

describe("VerdictPanel", () => {
  it.each([
    ["strong_fit", "strong match"],
    ["likely_fit", "likely match"],
    ["edge_case", "needs human review"],
    ["not_eligible", "does not fit"],
  ] as const)("renders the %s verdict heading", (band, textMatch) => {
    render(<VerdictPanel verdict={baseVerdict(band)} />);
    expect(
      screen.getByRole("heading", { name: new RegExp(textMatch, "i") }),
    ).toBeInTheDocument();
  });

  it("strong_fit and not_eligible receive visibly different panel treatments", () => {
    const { rerender, container } = render(
      <VerdictPanel verdict={baseVerdict("strong_fit")} />,
    );
    const strongSection = container.querySelector(
      '[data-verdict-band="strong_fit"]',
    ) as HTMLElement;
    const strongBorder = getPanelBorder(strongSection);

    rerender(<VerdictPanel verdict={baseVerdict("not_eligible")} />);
    const notEligibleSection = container.querySelector(
      '[data-verdict-band="not_eligible"]',
    ) as HTMLElement;
    const notEligibleBorder = getPanelBorder(notEligibleSection);

    // Color is different.
    expect(strongBorder.color).not.toBe(notEligibleBorder.color);
    // Weight is different (strong_fit is emphasized).
    expect(strongBorder.width).not.toBe(notEligibleBorder.width);
  });

  it("does not rely on colour alone: every band carries a distinct icon", () => {
    const seenPaths = new Set<string>();

    for (const band of [
      "strong_fit",
      "likely_fit",
      "edge_case",
      "not_eligible",
    ] as VerdictBand[]) {
      const { container } = render(
        <VerdictPanel verdict={baseVerdict(band)} />,
      );
      const section = container.querySelector(
        `[data-verdict-band="${band}"]`,
      ) as HTMLElement;
      expect(section).toBeInTheDocument();

      const icon = section.querySelector('svg[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();

      // Use the first path's "d" as a fingerprint for the icon shape.
      const firstPath = icon?.querySelector("path");
      expect(firstPath).toHaveAttribute("d");
      const d = firstPath?.getAttribute("d") ?? "";
      expect(seenPaths.has(d)).toBe(false);
      seenPaths.add(d);
    }

    expect(seenPaths.size).toBe(4);
  });

  it("renders the verdict title larger than secondary card titles would be", () => {
    render(<VerdictPanel verdict={baseVerdict("strong_fit")} />);
    const heading = screen.getByRole("heading", { name: /strong match/i });
    expect(heading.style.fontSize).toBe("clamp(2.2rem, 6vw, 3.5rem)");
  });

  it("never renders a numeric score or probability", () => {
    render(<VerdictPanel verdict={baseVerdict("strong_fit")} />);
    expect(screen.queryByText(/\d+%/)).toBeNull();
    expect(screen.queryByText(/probability/i)).toBeNull();
    expect(screen.queryByText(/score/i)).toBeNull();
  });
});

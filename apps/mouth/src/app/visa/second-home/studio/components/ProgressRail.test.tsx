import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressRail } from "./ProgressRail";

function ariaPercent(progressbar: HTMLElement): number {
  const now = Number(progressbar.getAttribute("aria-valuenow"));
  const min = Number(progressbar.getAttribute("aria-valuemin"));
  const max = Number(progressbar.getAttribute("aria-valuemax"));

  return ((now - min) / (max - min)) * 100;
}

function visualPercent(progressbar: HTMLElement): number {
  const soundings = progressbar.querySelectorAll(".bz-shs-progress-sounding");
  const reached = progressbar.querySelectorAll(
    '[data-progress-reached="true"]',
  );

  return (reached.length / soundings.length) * 100;
}

describe("ProgressRail", () => {
  it.each([
    { step: 1, expected: 100 / 6 },
    { step: 3, expected: 50 },
    { step: 6, expected: 100 },
  ])(
    "keeps visual and ARIA progress aligned at step $step of 6",
    ({ step, expected }) => {
      render(<ProgressRail step={step} total={6} />);
      const progressbar = screen.getByRole("progressbar");

      expect(visualPercent(progressbar)).toBeCloseTo(expected, 5);
      expect(ariaPercent(progressbar)).toBeCloseTo(expected, 5);
      expect(visualPercent(progressbar)).toBeCloseTo(
        ariaPercent(progressbar),
        5,
      );
    },
  );

  it("has one meaningful accessible name without repeating the visible label", () => {
    render(<ProgressRail step={2} total={6} />);

    const progressbar = screen.getByRole("progressbar", {
      name: "Interview progress",
    });
    const visibleLabel = screen.getByText("Step 2 of 6");

    expect(progressbar).toHaveAttribute("aria-label", "Interview progress");
    expect(progressbar).not.toHaveAttribute("aria-labelledby");
    expect(visibleLabel).toHaveAttribute("aria-hidden", "true");
  });

  it("recomputes safely when the adaptive branch changes total", () => {
    const { rerender } = render(<ProgressRail step={3} total={6} />);

    for (const props of [
      { step: 3, total: 5 },
      { step: 6, total: 5 },
      { step: 1, total: 0 },
    ]) {
      rerender(<ProgressRail {...props} />);
      const progressbar = screen.getByRole("progressbar");
      const visual = visualPercent(progressbar);
      const aria = ariaPercent(progressbar);

      expect(visual).toBeGreaterThanOrEqual(0);
      expect(visual).toBeLessThanOrEqual(100);
      expect(aria).toBeGreaterThanOrEqual(0);
      expect(aria).toBeLessThanOrEqual(100);
      expect(visual).toBeCloseTo(aria, 5);
      expect(
        Number(progressbar.getAttribute("aria-valuenow")),
      ).toBeLessThanOrEqual(Number(progressbar.getAttribute("aria-valuemax")));
    }
  });

  it("distinguishes reached and pending soundings by shape as well as colour", () => {
    const { container } = render(<ProgressRail step={3} total={6} />);
    const progressbar = screen.getByRole("progressbar");
    const style = container.querySelector("style")?.textContent ?? "";

    expect(
      progressbar.querySelectorAll('[data-state="complete"]'),
    ).toHaveLength(2);
    expect(progressbar.querySelectorAll('[data-state="current"]')).toHaveLength(
      1,
    );
    expect(progressbar.querySelectorAll('[data-state="pending"]')).toHaveLength(
      3,
    );
    expect(style).toMatch(
      /data-state="complete"[\s\S]*?border-top:\s*3px solid/,
    );
    expect(style).toMatch(
      /data-state="pending"[\s\S]*?border-top:\s*3px dashed/,
    );
    expect(style).toMatch(
      /data-state="pending"[\s\S]*?::after[\s\S]*?border:\s*2px solid/,
    );
  });

  it("removes every sounding transition under reduced motion", () => {
    const { container } = render(<ProgressRail step={2} total={6} />);
    const style = container.querySelector("style")?.textContent ?? "";

    expect(style).toMatch(
      /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/,
    );
    expect(style).toMatch(
      /prefers-reduced-motion[\s\S]*?\.bz-shs-progress-sounding::before,[\s\S]*?\.bz-shs-progress-sounding::after\s*\{[\s\S]*?transition:\s*none\s*!important/,
    );
  });
});

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { NextSteps } from "./NextSteps";

const HANDOFF = "https://wa.me/000?text=test";
const text = (hasDeadline = true) => {
  const { container } = render(
    <NextSteps handoffHref={HANDOFF} hasDeadline={hasDeadline} />,
  );
  return container.textContent ?? "";
};

/**
 * A DURATION is the single thing this block must never acquire. The corner's
 * banned list forbids "dijamin 24 jam"; this repo has already retired one
 * unmeasured response-time promise from another surface (`TrustBand`'s
 * docblock records it); and a funnel that says "usually about a week" has made
 * a commitment no part of this system measures.
 *
 * The regex is deliberately narrow — a NUMBER adjacent to a time unit — so it
 * convicts "3 working days" and leaves "the date above" alone. `voa-copy.guard`
 * already scans this file for the closed banned-claims list; this covers the
 * shape that list cannot express.
 */
const DURATION_RE =
  /\b(?:\d+|one|two|three|four|five|six|seven|ten|a few|several|an?)[\s-]*(?:business |working |calendar )?(?:second|minute|hour|day|week|month|jam|menit|hari|minggu|bulan)s?\b/i;

describe("NextSteps — what it says", () => {
  it("renders four steps and three limits", () => {
    render(<NextSteps handoffHref={HANDOFF} hasDeadline />);
    // Each list carries its own heading as accessible name: a screen reader
    // that lands on the limits hears WHICH list it is in, not "list, 3 items".
    const steps = screen.getByRole("list", { name: "What happens next" });
    const limits = screen.getByRole("list", { name: "What we cannot promise" });
    expect(steps.querySelectorAll("li")).toHaveLength(4);
    expect(limits.querySelectorAll("li")).toHaveLength(3);
  });

  it("names both halves — the commitment AND its boundary", () => {
    render(<NextSteps handoffHref={HANDOFF} hasDeadline />);
    expect(screen.getByText("What happens next")).toBeInTheDocument();
    expect(screen.getByText("What we cannot promise")).toBeInTheDocument();
  });

  it("says out loud that the decision is not ours", () => {
    expect(text()).toMatch(/decision is Immigration's, not ours/i);
  });

  /**
   * `[hash]/page.tsx` renders the clock only when the verdict carries a
   * `published_filing_deadline`. Without one there is no date above, so the
   * block must not point at one.
   */
  it("points at 'the date above' only when a date is actually above", () => {
    expect(text(true)).toMatch(/the date above/);
    expect(text(false)).not.toMatch(/(?:the|that) date above/i);
    expect(text(false)).toMatch(/published filing deadline/i);
  });

  it("carries the handoff as a real link", () => {
    render(<NextSteps handoffHref={HANDOFF} hasDeadline />);
    expect(
      screen.getByRole("link", { name: /ask us anything before you pay/i }),
    ).toHaveAttribute("href", HANDOFF);
  });
});

describe("NextSteps — what it must never say", () => {
  it("quotes no duration anywhere", () => {
    expect(text()).not.toMatch(DURATION_RE);
  });

  it("GUILTY: the regex catches the shapes a duration actually takes", () => {
    for (const bad of [
      "approved in 3 working days",
      "usually about a week",
      "dijamin 24 jam",
      "ready in two weeks",
      "filed within 48 hours",
    ]) {
      expect(DURATION_RE.test(bad), bad).toBe(true);
    }
  });

  it("quotes no duration in the no-deadline branch either", () => {
    expect(text(false)).not.toMatch(DURATION_RE);
  });

  it("INNOCENT: it does not convict the prose this block actually uses", () => {
    for (const ok of [
      "the date above is the counter's published filing deadline",
      "Pay once, the price shown above.",
      "We prepare and file your application at the office the date above is published by.",
      "You follow it like a parcel, and the result reaches the email you gave us.",
    ]) {
      expect(DURATION_RE.test(ok), ok).toBe(false);
    }
  });

  it("promises no approval and no likelihood of one", () => {
    expect(text()).not.toMatch(
      /guarantee|guaranteed|usually approved|always approved|approval rate|success rate|never rejected/i,
    );
  });

  it("names no individual — file ownership is not wired yet, so it is not claimed", () => {
    // A capitalised given name followed by "will" / "handles" / "is your".
    expect(text()).not.toMatch(
      /\b[A-Z][a-z]{2,}\s+(?:will|handles|is your|takes over)\b/,
    );
  });
});

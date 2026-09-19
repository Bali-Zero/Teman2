import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  SafeClockHero,
  civilDaysBetween,
  formatCivilDay,
  safeClockDaysLeft,
  safeClockState,
  witaCivilDay,
} from "./SafeClock";

const HANDOFF = "https://wa.me/000?text=test";

describe("witaCivilDay — the day is Bali's, not the runtime's", () => {
  /**
   * The whole reason this function exists. 17:30Z is still 7 September in
   * London and already 8 September in Denpasar (WITA = UTC+8, no DST), and
   * the counter a visitor files at keeps Denpasar's calendar. A naive
   * `toISOString().slice(0,10)` — the shape this replaces — returns
   * "2026-09-07" here, so this assertion is its own guilt control: it fails
   * the moment someone drops the explicit timeZone.
   */
  it("reads WITA's day, not UTC's, in the eight hours they disagree", () => {
    expect(witaCivilDay(new Date("2026-09-07T17:30:00Z"))).toBe("2026-09-08");
    expect(new Date("2026-09-07T17:30:00Z").toISOString().slice(0, 10)).toBe(
      "2026-09-07",
    );
  });

  it("agrees with UTC for the other sixteen hours (innocence control)", () => {
    expect(witaCivilDay(new Date("2026-09-08T03:00:00Z"))).toBe("2026-09-08");
  });
});

describe("civilDaysBetween — whole calendar days, no zone term", () => {
  it("counts across a month boundary", () => {
    expect(civilDaysBetween("2026-08-30", "2026-09-02")).toBe(3);
  });

  it("counts across a leap day", () => {
    expect(civilDaysBetween("2028-02-28", "2028-03-01")).toBe(2);
  });

  it("is zero on the same day and negative after it", () => {
    expect(civilDaysBetween("2026-09-08", "2026-09-08")).toBe(0);
    expect(civilDaysBetween("2026-09-09", "2026-09-08")).toBe(-1);
  });

  it("returns null on a string it cannot read, rather than a number", () => {
    expect(civilDaysBetween("not-a-day", "2026-09-08")).toBeNull();
    expect(civilDaysBetween("2026-09-08", "08/09/2026")).toBeNull();
  });
});

describe("safeClockState — four inputs, four distinct states", () => {
  it("bands at 0, 3 and 4", () => {
    expect(safeClockState(-1)).toBe("passed");
    expect(safeClockState(0)).toBe("today");
    expect(safeClockState(1)).toBe("soon");
    expect(safeClockState(3)).toBe("soon");
    expect(safeClockState(4)).toBe("ample");
  });

  /**
   * Mandate accent 4: never two states in one visual identity. The rendered
   * proof is the class-suffix check below; this is the logical half —
   * collapsing any two bands into one name trips it.
   */
  it("never returns the same state for two different bands", () => {
    const names = [-5, 0, 2, 10].map(safeClockState);
    expect(new Set(names).size).toBe(4);
  });
});

describe("formatCivilDay — a civil day renders as the day it was written", () => {
  it("does not slide a date-only ISO west", () => {
    const out = formatCivilDay("2026-09-08");
    expect(out).toContain("8 September 2026");
    expect(out).not.toContain("7 September");
  });

  it("passes an unreadable string through untouched", () => {
    expect(formatCivilDay("soon")).toBe("soon");
  });
});

describe("safeClockDaysLeft", () => {
  it("measures from WITA's today", () => {
    // 17:30Z on the 7th is already the 8th in Bali, so a deadline of the 10th
    // is two days out, not three.
    expect(
      safeClockDaysLeft("2026-09-10", new Date("2026-09-07T17:30:00Z")),
    ).toBe(2);
  });
});

describe("SafeClockHero — rendered states", () => {
  const renderAt = (deadline: string, nowIso: string) =>
    render(
      <SafeClockHero
        deadline={deadline}
        now={new Date(nowIso)}
        handoffHref={HANDOFF}
      />,
    );

  it("ample: shows the count and takes the ample identity", () => {
    const { container } = renderAt("2026-09-20", "2026-09-08T03:00:00Z");
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("days to file")).toBeInTheDocument();
    expect(container.querySelector(".voa-clock--ample")).not.toBeNull();
  });

  it("soon: a single day reads 'day', not 'days'", () => {
    const { container } = renderAt("2026-09-09", "2026-09-08T03:00:00Z");
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("day to file")).toBeInTheDocument();
    expect(container.querySelector(".voa-clock--soon")).not.toBeNull();
  });

  it("today: no count, the word leads, and the status identity is its own", () => {
    const { container } = renderAt("2026-09-08", "2026-09-08T03:00:00Z");
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(container.querySelector(".voa-clock__num")).toBeNull();
    expect(container.querySelector(".voa-clock--today")).not.toBeNull();
  });

  it("passed: renders no countdown at all and hands over to a person", () => {
    const { container } = renderAt("2026-09-01", "2026-09-08T03:00:00Z");
    expect(container.querySelector(".voa-clock__num")).toBeNull();
    expect(container.querySelector(".voa-clock__count")).toBeNull();
    expect(container.querySelector(".voa-clock--passed")).not.toBeNull();
    expect(
      screen.getByRole("link", { name: /message the visa desk/i }),
    ).toHaveAttribute("href", HANDOFF);
  });

  it("the four states take four different classes (guilt control for accent 4)", () => {
    const classes = [
      "2026-09-20",
      "2026-09-09",
      "2026-09-08",
      "2026-09-01",
    ].map((d) => {
      const { container, unmount } = renderAt(d, "2026-09-08T03:00:00Z");
      const el = container.querySelector(".voa-clock") as HTMLElement;
      const mod = [...el.classList].find((c) => c.startsWith("voa-clock--"));
      unmount();
      return mod;
    });
    expect(new Set(classes).size).toBe(4);
  });

  it("renders nothing rather than inventing a number on an unreadable deadline", () => {
    const { container } = renderAt("whenever", "2026-09-08T03:00:00Z");
    expect(container.querySelector(".voa-clock")).toBeNull();
  });

  /**
   * The internal name of this mechanism, and every checkpoint that is not the
   * published one, are forbidden in customer copy (`voa-copy.guard.test.ts`
   * §2 scans the source; this scans the DOM this component actually produced,
   * which is the half a source scan cannot see once a string is composed).
   */
  it("never renders an internal checkpoint name", () => {
    for (const d of ["2026-09-20", "2026-09-08", "2026-09-01"]) {
      const { container, unmount } = renderAt(d, "2026-09-08T03:00:00Z");
      expect(container.textContent).not.toMatch(
        /Safe Clock|D-14|D-10|D-7|D-3\b|D-1\b/i,
      );
      unmount();
    }
  });

  it("names the office on every branch it shows a date on", () => {
    for (const d of ["2026-09-20", "2026-09-08", "2026-09-01"]) {
      const { container, unmount } = renderAt(d, "2026-09-08T03:00:00Z");
      expect(container.textContent).toContain("Ngurah Rai");
      unmount();
    }
  });
});

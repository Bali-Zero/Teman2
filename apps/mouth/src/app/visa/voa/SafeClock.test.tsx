import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

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
    expect(screen.getByText("day left to file")).toBeInTheDocument();
    expect(container.querySelector(".voa-clock--soon")).not.toBeNull();
  });

  /**
   * The word is the second of the two axes that separate `ample` from `soon`
   * (the first is the rule width; their colours are 1.11:1 apart and cannot
   * carry it — see the pairwise separability rows in
   * `voa-contrast.computed.guard.test.tsx`). Sharing one string here is what
   * collapsed the two states in the first shipped version, so the guard is an
   * inequality, not a pair of literals: rewording either one keeps passing,
   * making them equal does not.
   */
  it("ample and soon never share their word", () => {
    const wordAt = (deadline: string) => {
      const { container, unmount } = renderAt(deadline, "2026-09-08T03:00:00Z");
      const w = container.querySelector(".voa-clock__unit")?.textContent;
      unmount();
      return w;
    };
    const ample = wordAt("2026-09-20");
    const soon = wordAt("2026-09-10");
    expect(ample).toBeTruthy();
    expect(soon).toBeTruthy();
    expect(soon).not.toBe(ample);
  });

  /**
   * The handoff is a control on its own row. Its predecessor was an inline
   * `<a>` carrying `min-height: 48px`, which broke the note into three
   * fragments on the promoted build at 390px while every unit test stayed
   * green. jsdom cannot reproduce that layout, so what is pinned instead is
   * the structural property that made it possible: the anchor is a SIBLING of
   * the note, never a descendant of it.
   */
  it("the handoff is a sibling of the prose, never inside it", () => {
    for (const d of ["2026-09-20", "2026-09-08", "2026-09-01"]) {
      const { container, unmount } = renderAt(d, "2026-09-08T03:00:00Z");
      const link = container.querySelector("a")!;
      expect(link, d).not.toBeNull();
      expect(
        link.closest("p"),
        `${d}: handoff must not live inside a <p>`,
      ).toBeNull();
      expect(link.className).toContain("voa-clock__handoff");
      unmount();
    }
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

/**
 * The live path — no `now` prop, so the poll, the `visibilitychange` listener
 * and the cleanup are the ones production runs.
 *
 * Until this block existed nothing rendered the component without the frozen
 * seam, so the claim that the count stops being stale across WITA midnight was
 * argued in a docblock and proved nowhere. The seam being well-behaved is not
 * evidence about the path it bypasses.
 */
describe("SafeClockHero — the unfrozen clock", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("crosses WITA midnight without a reload", () => {
    vi.useFakeTimers();
    // 03:00Z on the 8th: the same civil day in Bali and in UTC.
    vi.setSystemTime(new Date("2026-09-08T03:00:00Z"));
    render(<SafeClockHero deadline="2026-09-20" handoffHref={HANDOFF} />);
    expect(screen.getByText("12")).toBeInTheDocument();

    // 16:30Z is 00:30 on the 9th in Denpasar — still the 8th in UTC, which is
    // why a naive clock would sit here showing 12 for another seven and a half
    // hours.
    vi.setSystemTime(new Date("2026-09-08T16:30:00Z"));
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByText("11")).toBeInTheDocument();
  });

  it("re-reads when a backgrounded tab comes back, without waiting for the tick", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T03:00:00Z"));
    render(<SafeClockHero deadline="2026-09-20" handoffHref={HANDOFF} />);
    expect(screen.getByText("12")).toBeInTheDocument();

    vi.setSystemTime(new Date("2026-09-09T03:00:00Z"));
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(screen.getByText("11")).toBeInTheDocument();
  });

  it("GUILT CONTROL: the interval is torn down on unmount", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T03:00:00Z"));
    const clearSpy = vi.spyOn(window, "clearInterval");
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const { unmount } = render(
      <SafeClockHero deadline="2026-09-20" handoffHref={HANDOFF} />,
    );
    const pending = vi.getTimerCount();
    expect(pending).toBeGreaterThan(0);
    unmount();
    expect(clearSpy).toHaveBeenCalled();
    expect(removeSpy).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );
    expect(vi.getTimerCount()).toBeLessThan(pending);
    clearSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("GUILT CONTROL: a frozen clock installs no timer at all", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-08T03:00:00Z"));
    render(
      <SafeClockHero
        deadline="2026-09-20"
        now={new Date("2026-09-08T03:00:00Z")}
        handoffHref={HANDOFF}
      />,
    );
    expect(vi.getTimerCount()).toBe(0);
  });
});

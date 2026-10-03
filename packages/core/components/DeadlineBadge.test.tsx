import { describe, it, expect, afterEach, vi } from "vitest";
import { render } from "@testing-library/react";
import { DeadlineBadge } from "./DeadlineBadge";

describe("DeadlineBadge", () => {
  it("renders 'in Xd' when deadline is future", () => {
    const future = new Date(Date.now() + 5 * 86400_000);
    const { getByText } = render(<DeadlineBadge date={future} />);
    expect(getByText(/in 5d/)).toBeTruthy();
  });

  it("renders 'overdue' when deadline passed", () => {
    const past = new Date(Date.now() - 3 * 86400_000);
    const { getByText } = render(<DeadlineBadge date={past} />);
    expect(getByText(/overdue/i)).toBeTruthy();
  });

  it("maps days-left to a semantic state token", () => {
    const in2d = new Date(Date.now() + 2 * 86400_000);
    const { container } = render(<DeadlineBadge date={in2d} />);
    const fill = container.querySelector("circle[data-role='fill']");
    expect(fill?.getAttribute("stroke")).toBe("var(--state-danger)");
  });
});

// gate-7583 fix-forward F3: "days left" is a WITA (Asia/Makassar, UTC+8, no
// DST) calendar-day count, not a raw millisecond diff — so a due date does
// not drop and badges are not off-by-one before 08:00 WITA.
describe("DeadlineBadge — WITA calendar-day count (F3)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("09:00 WITA on the due day: still 'in 0d', not overdue and not rolled to the next day", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-15T01:00:00Z")); // 09:00 WITA
    const { getByText } = render(
      <DeadlineBadge date={new Date("2026-10-15T00:00:00Z")} />,
    );
    expect(getByText(/in 0d/)).toBeTruthy();
  });

  it("07:10 WITA 28 Sep: a due date on 30 Sep reads 'in 2d', not 3", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-27T23:10:00Z")); // 07:10 WITA 28 Sep
    const { getByText } = render(
      <DeadlineBadge date={new Date("2026-09-30T00:00:00Z")} />,
    );
    expect(getByText(/in 2d/)).toBeTruthy();
  });
});

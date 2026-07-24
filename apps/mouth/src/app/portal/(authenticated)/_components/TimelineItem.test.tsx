import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { TimelineItem } from "./TimelineItem";
import type { TimelineEntry } from "@/lib/api/types/timeline.types";

const baseEntry: TimelineEntry = {
  id: "t1",
  type: "message",
  occurredAt: new Date().toISOString(),
  title: "Test entry",
  description: "Something happened",
};

describe("TimelineItem (WS3 · GARUDA Day Edition)", () => {
  it("maps message entries to the info state token", () => {
    const { container } = render(
      <TimelineItem entry={baseEntry} isLast={false} />,
    );
    expect(container.innerHTML).toContain("var(--state-info)");
    expect(container.innerHTML).not.toContain("neon-blue");
  });

  it("maps deadline entries to the danger state token", () => {
    const entry: TimelineEntry = { ...baseEntry, id: "t2", type: "deadline" };
    const { container } = render(<TimelineItem entry={entry} isLast={false} />);
    expect(container.innerHTML).toContain("var(--state-danger)");
    expect(container.innerHTML).not.toContain("neon-rose");
  });

  it("maps future entries to the warning state token", () => {
    const entry: TimelineEntry = {
      ...baseEntry,
      id: "t3",
      type: "document",
      isFuture: true,
      occurredAt: new Date(Date.now() + 5 * 86400000).toISOString(),
    };
    const { container } = render(<TimelineItem entry={entry} isLast={false} />);
    expect(container.innerHTML).toContain("var(--state-warning)");
    expect(container.innerHTML).not.toContain("neon-amber");
  });

  it("reply link uses the daylight copper text step (AA small text)", () => {
    const entry: TimelineEntry = {
      ...baseEntry,
      id: "t4",
      type: "message",
      status: "team_to_client",
    };
    render(<TimelineItem entry={entry} isLast={false} />);
    const reply = screen.getByText("Reply").closest("button");
    expect(reply).not.toBeNull();
    expect(reply?.className).toContain("text-[var(--bz-copper-text)]");
    // white hover is invisible on paper — must hover to theme text instead
    expect(reply?.className).not.toContain("hover:text-white");
    expect(reply?.className).toContain("hover:text-[var(--tx-pure)]");
  });

  it("relative-date chips use state tokens, not dark-theme utilities", () => {
    const today: TimelineEntry = { ...baseEntry, id: "t5" };
    const { container } = render(<TimelineItem entry={today} isLast={false} />);
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(container.innerHTML).toContain("var(--state-success)");
    expect(container.innerHTML).not.toContain("text-emerald-400");
    expect(container.innerHTML).not.toContain("text-amber-400");
  });
});

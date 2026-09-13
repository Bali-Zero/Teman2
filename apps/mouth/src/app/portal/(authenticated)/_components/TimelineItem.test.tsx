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

describe("TimelineItem (SAETTA-R19P · concept-F spine)", () => {
  it("gives team events a hollow slate dot", () => {
    const { container } = render(
      <TimelineItem entry={baseEntry} isLast={false} />,
    );
    expect(container.innerHTML).toContain("border-[var(--state-info)]");
    expect(container.innerHTML).toContain("bg-[var(--bz-base)]");
    expect(container.innerHTML).not.toContain("crystal-stat-card");
  });

  it("gives client uploads a filled copper dot", () => {
    const entry: TimelineEntry = { ...baseEntry, id: "t2", type: "document" };
    const { container } = render(<TimelineItem entry={entry} isLast={false} />);
    expect(container.innerHTML).toContain("bg-[var(--bz-copper)]");
  });

  it("gives a message the client sent a filled copper dot", () => {
    const entry: TimelineEntry = {
      ...baseEntry,
      id: "t3",
      status: "client_to_team",
    };
    const { container } = render(<TimelineItem entry={entry} isLast={false} />);
    expect(container.innerHTML).toContain("bg-[var(--bz-copper)]");
  });

  it("keeps deadlines on the spine without any danger fill", () => {
    const entry: TimelineEntry = { ...baseEntry, id: "t4", type: "deadline" };
    const { container } = render(<TimelineItem entry={entry} isLast={false} />);
    expect(container.innerHTML).not.toContain("var(--state-danger)");
    expect(screen.getByText("Test entry")).toBeInTheDocument();
  });

  it("marks a future entry with the word Upcoming, not a warning fill", () => {
    const entry: TimelineEntry = {
      ...baseEntry,
      id: "t5",
      type: "document",
      isFuture: true,
      occurredAt: new Date(Date.now() + 5 * 86400000).toISOString(),
    };
    const { container } = render(<TimelineItem entry={entry} isLast={false} />);
    expect(screen.getByText(/Upcoming/)).toBeInTheDocument();
    expect(container.innerHTML).not.toContain("var(--state-warning)");
  });

  it("reply link uses the daylight copper text step (AA small text)", () => {
    const entry: TimelineEntry = {
      ...baseEntry,
      id: "t6",
      type: "message",
      status: "team_to_client",
    };
    render(<TimelineItem entry={entry} isLast={false} />);
    const reply = screen.getByText("Reply").closest("button");
    expect(reply).not.toBeNull();
    expect(reply?.className).toContain("text-[var(--bz-copper-text)]");
    expect(reply?.className).not.toContain("hover:text-white");
    expect(reply?.className).toContain("hover:text-[var(--tx-pure)]");
  });

  it("keeps the relative day as quiet text, not a coloured chip", () => {
    const today: TimelineEntry = { ...baseEntry, id: "t7" };
    const { container } = render(<TimelineItem entry={today} isLast={false} />);
    expect(screen.getByText(/Today/)).toBeInTheDocument();
    expect(container.innerHTML).not.toContain("var(--state-success)");
    expect(container.innerHTML).not.toContain("text-amber-400");
  });
});

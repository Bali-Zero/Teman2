import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LiveActivityFeed } from "../LiveActivityFeed";
import type { LiveActivityEvent } from "@/types/dashboard-role.types";

const mockEvents: LiveActivityEvent[] = [
  {
    id: "1",
    type: "critical",
    icon: "🚨",
    text: "KITAS scade in 5 giorni",
    tag: "CRITICO",
    timestamp: "14:52",
    userId: "user-1",
  },
  {
    id: "2",
    type: "ok",
    icon: "✅",
    text: "Fattura pagata",
    tag: "PAGATO",
    timestamp: "14:48",
    userId: "user-1",
  },
  {
    id: "3",
    type: "info",
    icon: "📄",
    text: "Documento caricato",
    tag: "DOC",
    timestamp: "14:32",
    userId: "user-2",
  },
];

describe("LiveActivityFeed", () => {
  it("renders the LIVE ACTIVITY label", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText("LIVE ACTIVITY")).toBeInTheDocument();
  });

  it("renders all events", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText(/KITAS scade/)).toBeInTheDocument();
    expect(screen.getByText(/Fattura pagata/)).toBeInTheDocument();
    expect(screen.getByText(/Documento caricato/)).toBeInTheDocument();
  });

  it("shows event count", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText(/3 eventi/)).toBeInTheDocument();
  });

  it("renders skeleton when isLoading", () => {
    const { container } = render(
      <LiveActivityFeed events={[]} isLoading={true} />,
    );
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
  });

  it("renders tag badges", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText("CRITICO")).toBeInTheDocument();
    expect(screen.getByText("PAGATO")).toBeInTheDocument();
  });

  it("renders event timestamps", () => {
    render(<LiveActivityFeed events={mockEvents} isLoading={false} />);
    expect(screen.getByText("14:52")).toBeInTheDocument();
  });
});

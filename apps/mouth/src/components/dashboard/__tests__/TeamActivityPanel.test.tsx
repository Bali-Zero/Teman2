import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TeamActivityPanel, type TeamMemberStats } from "../TeamActivityPanel";

const member = (over: Partial<TeamMemberStats> = {}): TeamMemberStats => ({
  email: "ari.firda@balizero.com",
  name: "Ari Firda",
  role: "consultant",
  days_worked: 18,
  crm_actions: 72,
  practices_completed: 5,
  practices_active: 3,
  practices_revenue: 45_000_000,
  ...over,
});

describe("TeamActivityPanel", () => {
  it("renders only the live metric columns", () => {
    render(
      <TeamActivityPanel
        members={[member()]}
        overview={{ active_today: 2 }}
        isLoading={false}
      />,
    );
    for (const label of ["Member", "Days", "CRM", "Done", "Revenue"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("does not render the dead always-zero columns (P0.2)", () => {
    render(
      <TeamActivityPanel
        members={[member()]}
        overview={{ active_today: 2 }}
        isLoading={false}
      />,
    );
    for (const dead of [
      "Convos",
      "Messages",
      "Emails Out",
      "Emails In",
      "KB Views",
      "KB DL",
    ]) {
      expect(screen.queryByText(dead)).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/total messages/i)).not.toBeInTheDocument();
  });

  it("renders member values and revenue", () => {
    render(
      <TeamActivityPanel
        members={[member()]}
        overview={{ active_today: 1 }}
        isLoading={false}
      />,
    );
    expect(screen.getByText("Ari Firda")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Rp 45M")).toBeInTheDocument();
  });

  it("shows the empty state when there are no members", () => {
    render(
      <TeamActivityPanel members={[]} overview={null} isLoading={false} />,
    );
    expect(screen.getByText("No team data")).toBeInTheDocument();
  });
});

import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ComplianceRadar } from "./ComplianceRadar";
import type { ComplianceAlert } from "./ComplianceRadar";

const ALERTS: ComplianceAlert[] = [
  {
    id: "a1",
    title: "KITAS expiry < 30 days",
    detail: "CLI-2207 · renewal pack ready",
    severity: "critical",
    timeLeft: "6d",
  },
  {
    id: "a2",
    title: "Passport validity < 6 months",
    detail: "CLI-2089 · blocks KITAP filing",
    severity: "urgent",
    timeLeft: "21d",
  },
  {
    id: "a3",
    title: "IMTA renewal window opens",
    severity: "warning",
    timeLeft: "34d",
  },
  {
    id: "a4",
    title: "PP 28/2025 OSS update",
    severity: "info",
    timeLeft: "INFO",
  },
];

describe("ComplianceRadar", () => {
  it("renders a row per alert with prop-driven content", () => {
    const { container, getByText } = render(
      <ComplianceRadar alerts={ALERTS} />,
    );
    expect(container.querySelectorAll("[data-role='alert-row']")).toHaveLength(
      4,
    );
    expect(getByText("KITAS expiry < 30 days")).toBeTruthy();
    expect(getByText("CLI-2207 · renewal pack ready")).toBeTruthy();
    expect(getByText("6d")).toBeTruthy();
  });

  it("maps severity to the dot's semantic token", () => {
    const { container } = render(<ComplianceRadar alerts={ALERTS} />);
    const dots = container.querySelectorAll("[data-role='severity-dot']");
    const bg = (i: number) => (dots[i] as HTMLElement).style.background;
    expect(bg(0)).toBe("var(--status-critical)");
    expect(bg(1)).toBe("var(--state-warning)");
    expect(bg(2)).toBe("var(--fact-badge-bg)");
    expect(bg(3)).toBe("var(--state-info)");
  });

  it("glows the critical dot only", () => {
    const { container } = render(<ComplianceRadar alerts={ALERTS} />);
    const dots = container.querySelectorAll("[data-role='severity-dot']");
    expect((dots[0] as HTMLElement).style.boxShadow).toBe(
      "0 0 9px var(--status-critical)",
    );
    expect((dots[1] as HTMLElement).style.boxShadow).toBe("none");
  });

  it("renders critical time-left strong via the dark-surface danger token", () => {
    const { container } = render(<ComplianceRadar alerts={ALERTS} />);
    const times = container.querySelectorAll("[data-role='alert-time-left']");
    const crit = times[0] as HTMLElement;
    const urgent = times[1] as HTMLElement;
    expect(crit.style.color).toBe("var(--state-danger)");
    expect(crit.style.fontWeight).toBe("700");
    expect(urgent.style.color).toBe("var(--text-secondary)");
    expect(urgent.style.fontWeight).toBe("");
  });

  it("omits the time block when timeLeft is absent", () => {
    const alerts: ComplianceAlert[] = [
      { id: "x", title: "LKPM Q2 filing window", severity: "info" },
    ];
    const { container } = render(<ComplianceRadar alerts={alerts} />);
    expect(container.querySelector("[data-role='alert-when']")).toBeNull();
    expect(container.querySelector("[data-role='alert-row']")).toBeTruthy();
  });

  it("renders a defined empty root when alerts is empty", () => {
    const { container } = render(<ComplianceRadar alerts={[]} />);
    expect(
      container.querySelector("[data-role='compliance-radar']"),
    ).toBeTruthy();
    expect(container.querySelectorAll("[data-role='alert-row']")).toHaveLength(
      0,
    );
  });
});

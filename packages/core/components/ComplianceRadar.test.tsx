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
    expect(bg(2)).toBe("var(--accent-gold-muted)");
    expect(bg(3)).toBe("var(--state-info)");
  });

  it("renders a visible severity label per row with severity token color", () => {
    const { container } = render(<ComplianceRadar alerts={ALERTS} />);
    const labels = Array.from(
      container.querySelectorAll("[data-role='severity-label']"),
    ) as HTMLElement[];
    // sorted order: critical > urgent > warning > info
    expect(labels.map((el) => el.textContent)).toEqual([
      "CRITICAL",
      "URGENT",
      "WARN",
      "INFO",
    ]);
    // visible text colored by severity token (critical reads the
    // dark-surface-safe --state-danger, never --status-critical as text)
    expect(labels[0].style.color).toBe("var(--state-danger)");
    expect(labels[1].style.color).toBe("var(--state-warning)");
    expect(labels[2].style.color).toBe("var(--accent-gold-muted)");
    expect(labels[3].style.color).toBe("var(--state-info)");
    // visible label replaces the round-2 sr-only span
    expect(container.querySelector(".sr-only")).toBeNull();
  });

  it("sorts rows by severity rank, stable within ties, input unmutated", () => {
    const shuffled: ComplianceAlert[] = [
      { id: "i1", title: "Info first", severity: "info" },
      { id: "c1", title: "Crit A", severity: "critical" },
      { id: "w1", title: "Warn mid", severity: "warning" },
      { id: "u1", title: "Urgent", severity: "urgent" },
      { id: "c2", title: "Crit B", severity: "critical" },
    ];
    const { container } = render(<ComplianceRadar alerts={shuffled} />);
    const titles = Array.from(
      container.querySelectorAll("[data-role='alert-title']"),
    ).map((el) => el.textContent);
    expect(titles).toEqual([
      "Crit A",
      "Crit B",
      "Urgent",
      "Warn mid",
      "Info first",
    ]);
    expect(shuffled.map((a) => a.id)).toEqual(["i1", "c1", "w1", "u1", "c2"]);
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

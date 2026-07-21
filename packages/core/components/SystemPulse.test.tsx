import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SystemPulse, serviceBadge } from "./SystemPulse";
import type { SystemPulseService } from "./SystemPulse";

const SERVICES: SystemPulseService[] = [
  {
    id: "pg",
    label: "PostgreSQL",
    detail: "prod · ap-southeast",
    status: "ok",
    latencyMs: 12,
    barPct: 22,
  },
  {
    id: "kg",
    label: "Knowledge Graph",
    detail: "108,068 nodes",
    status: "down",
    latencyMs: 480,
    barPct: 96,
  },
];

describe("SystemPulse", () => {
  it("renders a row per service with prop-driven content", () => {
    const { container, getByText } = render(
      <SystemPulse services={SERVICES} />,
    );
    expect(
      container.querySelectorAll("[data-role='service-row']"),
    ).toHaveLength(2);
    expect(getByText("PostgreSQL")).toBeTruthy();
    expect(getByText("Knowledge Graph")).toBeTruthy();
    expect(getByText("prod · ap-southeast")).toBeTruthy();
    expect(getByText("12ms")).toBeTruthy();
  });

  it("derives the 2-letter mono badge from the label", () => {
    expect(serviceBadge("Knowledge Graph")).toBe("KG");
    expect(serviceBadge("Qdrant")).toBe("QD");
    const { container } = render(<SystemPulse services={SERVICES} />);
    const badges = container.querySelectorAll("[data-role='service-badge']");
    expect(badges[0].textContent).toBe("PO");
    expect(badges[1].textContent).toBe("KG");
  });

  it("maps status to semantic state tokens on value and bar fill", () => {
    const { container } = render(<SystemPulse services={SERVICES} />);
    const rows = container.querySelectorAll("[data-role='service-row']");
    const valueOf = (row: Element) =>
      row.querySelector("[data-role='service-latency-value']") as HTMLElement;
    const fillOf = (row: Element) =>
      row.querySelector("[data-role='service-bar-fill']") as HTMLElement;
    expect(valueOf(rows[0]).style.color).toBe("var(--state-success)");
    expect(fillOf(rows[0]).style.background).toBe("var(--state-success)");
    expect(valueOf(rows[1]).style.color).toBe("var(--state-danger)");
    expect(fillOf(rows[1]).style.background).toBe("var(--state-danger)");
  });

  it("idle reads the muted text token and shows the status word", () => {
    const idle: SystemPulseService[] = [
      { id: "ol", label: "Ollama", status: "idle", barPct: 4 },
    ];
    const { container, getByText } = render(<SystemPulse services={idle} />);
    const value = container.querySelector(
      "[data-role='service-latency-value']",
    ) as HTMLElement;
    expect(getByText("IDLE")).toBeTruthy();
    expect(value.style.color).toBe("var(--text-tertiary)");
  });

  it("clamps barPct to [0, 100] and omits the bar when barPct is absent", () => {
    const rows: SystemPulseService[] = [
      { id: "a", label: "Alpha", status: "ok", latencyMs: 1, barPct: 150 },
      { id: "b", label: "Beta", status: "ok", latencyMs: 2 },
    ];
    const { container } = render(<SystemPulse services={rows} />);
    const fill = container.querySelector(
      "[data-role='service-bar-fill']",
    ) as HTMLElement;
    expect(fill.style.width).toBe("100%");
    expect(
      container.querySelectorAll("[data-role='service-bar']"),
    ).toHaveLength(1);
  });

  it("exposes the status as visually-hidden text in every row", () => {
    const latencyLess: SystemPulseService[] = [
      { id: "ol", label: "Ollama", status: "idle", barPct: 4 },
    ];
    const { container } = render(
      <SystemPulse services={[...SERVICES, ...latencyLess]} />,
    );
    const rows = container.querySelectorAll("[data-role='service-row']");
    const srText = (row: Element) => row.querySelector(".sr-only")?.textContent;
    // latency-bearing rows: status is otherwise conveyed by color only
    expect(srText(rows[0])).toBe("Status: OK");
    expect(srText(rows[1])).toBe("Status: DOWN");
    // latency-less row still carries the accessible status text
    expect(srText(rows[2])).toBe("Status: IDLE");
  });

  it("renders a defined empty root when services is empty", () => {
    const { container } = render(<SystemPulse services={[]} />);
    expect(container.querySelector("[data-role='system-pulse']")).toBeTruthy();
    expect(
      container.querySelectorAll("[data-role='service-row']"),
    ).toHaveLength(0);
  });
});

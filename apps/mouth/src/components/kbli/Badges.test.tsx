import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PMABadge } from "./PMABadge";
import { RiskBadge } from "./RiskBadge";
import { TransitionBadge } from "./TransitionBadge";

describe("KBLI badges", () => {
  it("normalizes Indonesian risk categories into English labels", () => {
    const { rerender } = render(<RiskBadge category="Risiko Rendah" />);
    expect(screen.getByText("Low Risk")).toBeInTheDocument();

    rerender(<RiskBadge category="Menengah Rendah" size="sm" />);
    expect(screen.getByText("Medium-Low Risk")).toBeInTheDocument();

    rerender(<RiskBadge category="Menengah Tinggi" />);
    expect(screen.getByText("Medium-High Risk")).toBeInTheDocument();

    rerender(<RiskBadge riskCategory="Tinggi" />);
    expect(screen.getByText("High Risk")).toBeInTheDocument();

    rerender(<RiskBadge category="Custom advisory" />);
    expect(screen.getByText("Custom advisory Risk")).toBeInTheDocument();
  });

  it("renders PMA ownership status details", () => {
    const { rerender } = render(<PMABadge status="open" maxForeign={100} />);
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("· 100% Foreign")).toBeInTheDocument();

    rerender(<PMABadge status="restricted" maxForeign={49} size="sm" />);
    expect(screen.getByText("Restricted")).toBeInTheDocument();
    expect(screen.getByText("· Max 49%")).toBeInTheDocument();

    rerender(<PMABadge status="closed" maxForeign={0} />);
    expect(screen.getByText("Closed")).toBeInTheDocument();

    rerender(<PMABadge status="unknown" maxForeign={0} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("renders transition mapping labels and returns nothing for empty status", () => {
    const { container, rerender } = render(
      <TransitionBadge status="MATCH_LANGSUNG" />,
    );
    expect(screen.getByText("Direct Match")).toBeInTheDocument();

    rerender(<TransitionBadge status="CODICE_RINUMERATO" />);
    expect(screen.getByText("Renumbered")).toBeInTheDocument();

    rerender(<TransitionBadge status="MATCH_CON_AGGREGAZIONE" />);
    expect(screen.getByText("Aggregated")).toBeInTheDocument();

    rerender(<TransitionBadge status="BPS_ONLY" />);
    expect(screen.getByText("New in 2025")).toBeInTheDocument();

    rerender(<TransitionBadge status="" />);
    expect(container).toBeEmptyDOMElement();
  });
});

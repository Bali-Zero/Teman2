import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RiskBadge } from "./RiskBadge";

describe("RiskBadge — verificationPending qualifier (TRACK-P)", () => {
  it("marks the badge when the rows behind the tier are unverified", () => {
    render(<RiskBadge category="Menengah Rendah" verificationPending />);
    expect(screen.getByText("Medium-Low Risk")).toBeDefined();
    expect(screen.getByText("· pending verification")).toBeDefined();
  });

  it("innocence: a verified tier renders the plain badge, no qualifier", () => {
    render(<RiskBadge category="Rendah" />);
    expect(screen.getByText("Low Risk")).toBeDefined();
    expect(screen.queryByText("· pending verification")).toBeNull();
  });
});

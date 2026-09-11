import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { FunnelFrame } from "./FunnelFrame";

describe("FunnelFrame", () => {
  it("renders children, TrustBand, and CTAHandoff", () => {
    const { getByText, getByRole } = render(
      <FunnelFrame
        funnel="visa"
        sessionId="abc"
        step={{ current: 2, total: 5 }}
        trust={{ rating: "4.9", reviewCount: 1234 }}
      >
        <div>QUIZ_BODY</div>
      </FunnelFrame>,
    );
    expect(getByText("QUIZ_BODY")).toBeTruthy();
    expect(getByText(/4\.9/)).toBeTruthy();
    expect(getByRole("group", { name: /next actions/i })).toBeTruthy();
  });

  it("sets data-funnel on the container", () => {
    const { container } = render(
      <FunnelFrame funnel="kbli" sessionId="x">
        <span>body</span>
      </FunnelFrame>,
    );
    expect(container.firstChild).toHaveAttribute("data-funnel", "kbli");
  });
});

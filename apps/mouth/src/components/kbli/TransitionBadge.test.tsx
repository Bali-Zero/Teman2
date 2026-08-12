import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { TransitionBadge } from "./TransitionBadge";

describe("TransitionBadge — dark-theme tokens", () => {
  it("renders a labeled pill styled from a --kbli-* token, never a light-mode class", () => {
    const code = getCode("01111")!;
    const { container } = render(
      <TransitionBadge transition={code.transition} />,
    );
    expect(screen.getByText("Direct Match")).toBeDefined();
    const span = container.querySelector("span")!;
    // color comes from the theme token, not a hardcoded light-mode class
    expect(span.style.color).toContain("--kbli-pma-open");
    expect(span.getAttribute("class") ?? "").not.toMatch(
      /bg-(green|blue|amber|purple)-\d/,
    );
  });

  it("innocence: empty status renders nothing", () => {
    const { container } = render(
      <TransitionBadge
        transition={{
          mappingStatus: "",
          bpsCrosswalk: {
            codes: ["01111"],
            adjudicationStatus: "mechanical-only",
            inheritanceVerdict: "not-adjudicated",
          },
        }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("innocence: 01287 has no BPS ancestry and still renders no Direct Match badge", () => {
    const code = getCode("01287")!;
    expect(code.transition.mappingStatus).toBe("MATCH_LANGSUNG");
    expect(code.transition.bpsCrosswalk?.codes ?? []).toHaveLength(0);
    const { container } = render(
      <TransitionBadge transition={code.transition} />,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText("Direct Match")).toBeNull();
  });

  it("guilt: 03300 has sixteen BPS ancestors and renders no New in 2025 badge", () => {
    const code = getCode("03300")!;
    expect(code.transition.mappingStatus).toBe("BPS_ONLY");
    expect(code.transition.bpsCrosswalk?.codes).toHaveLength(16);
    const { container } = render(
      <TransitionBadge transition={code.transition} />,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText("New in 2025")).toBeNull();
  });

  it("innocence: a MATCH_LANGSUNG code with BPS ancestry keeps Direct Match", () => {
    const code = getCode("01111")!;
    expect(code.transition.mappingStatus).toBe("MATCH_LANGSUNG");
    expect(code.transition.bpsCrosswalk?.codes.length).toBeGreaterThan(0);
    render(<TransitionBadge transition={code.transition} />);
    expect(screen.getByText("Direct Match")).toBeInTheDocument();
  });
});

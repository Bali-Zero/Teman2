import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PathsCounter } from "./PathsCounter";

describe("PathsCounter", () => {
  it("renders only the interview-branch count when no breakdown is given", () => {
    render(<PathsCounter language="en" count={4} visible />);

    expect(screen.getByText("4")).toBeInTheDocument();
    expect(
      screen.queryByText(/paths serve your situation/i),
    ).not.toBeInTheDocument();
  });

  it("never shows a breakdown before the category has narrowed to one, even if one is given", () => {
    render(
      <PathsCounter
        language="en"
        count={10}
        visible
        productBreakdown={{ total: 5, selfService: 1, consultantRouted: 4 }}
      />,
    );

    expect(
      screen.queryByText(/paths serve your situation/i),
    ).not.toBeInTheDocument();
  });

  it("renders the split sentence with the exact numbers substituted", () => {
    render(
      <PathsCounter
        language="en"
        count={1}
        visible
        productBreakdown={{ total: 5, selfService: 1, consultantRouted: 4 }}
      />,
    );

    expect(
      screen.getByText(
        "5 paths serve your situation: 1 you complete here, 4 go through a consultant.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the all-self-service sentence when consultantRouted is 0", () => {
    render(
      <PathsCounter
        language="en"
        count={1}
        visible
        productBreakdown={{ total: 1, selfService: 1, consultantRouted: 0 }}
      />,
    );

    expect(
      screen.getByText("1 paths serve your situation — all completed here."),
    ).toBeInTheDocument();
  });

  it("renders the all-consultant sentence when selfService is 0", () => {
    render(
      <PathsCounter
        language="en"
        count={1}
        visible
        productBreakdown={{ total: 2, selfService: 0, consultantRouted: 2 }}
      />,
    );

    expect(
      screen.getByText(
        "2 paths serve your situation — all through a consultant.",
      ),
    ).toBeInTheDocument();
  });

  it("shows nothing extra for a category with no honest breakdown (e.g. diaspora)", () => {
    render(
      <PathsCounter language="en" count={1} visible productBreakdown={null} />,
    );

    expect(
      screen.queryByText(/paths serve your situation/i),
    ).not.toBeInTheDocument();
  });

  it("renders the Indonesian split sentence for a split case", () => {
    render(
      <PathsCounter
        language="id"
        count={1}
        visible
        productBreakdown={{ total: 19, selfService: 16, consultantRouted: 3 }}
      />,
    );

    expect(
      screen.getByText(
        "19 jalur sesuai situasi Anda: 16 dapat diselesaikan di sini, 3 melalui konsultan.",
      ),
    ).toBeInTheDocument();
  });
});

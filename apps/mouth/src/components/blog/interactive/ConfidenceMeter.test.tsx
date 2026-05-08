import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfidenceMeter } from "./ConfidenceMeter";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
}));

describe("ConfidenceMeter", () => {
  const items = [
    { label: "OSS data", value: 92, source: "OSS", note: "Fresh extract" },
    { label: "Field check", value: 74 },
    { label: "Registry match", value: 48 },
    { label: "Legacy source", value: 25 },
  ];

  it("renders detailed confidence rows with source notes and legend", () => {
    render(<ConfidenceMeter items={items} title="Reliability Matrix" />);

    expect(screen.getByText("Reliability Matrix")).toBeInTheDocument();
    expect(screen.getByText("OSS data")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("Source: OSS")).toBeInTheDocument();
    expect(screen.getByText("Fresh extract")).toBeInTheDocument();
    expect(screen.getByText("80-100%: High")).toBeInTheDocument();
    expect(screen.getByText("60-79%: Good")).toBeInTheDocument();
    expect(screen.getByText("40-59%: Moderate")).toBeInTheDocument();
    expect(screen.getByText("0-39%: Low")).toBeInTheDocument();
  });

  it("uses compact mode without the detailed header, notes, or legend", () => {
    render(
      <ConfidenceMeter
        items={[items[0]]}
        title="Hidden in compact"
        variant="compact"
      />,
    );

    expect(screen.getByText("OSS data")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.queryByText("Hidden in compact")).not.toBeInTheDocument();
    expect(screen.queryByText("Source: OSS")).not.toBeInTheDocument();
    expect(screen.queryByText("80-100%: High")).not.toBeInTheDocument();
  });

  it("can hide the legend in detailed mode", () => {
    render(<ConfidenceMeter items={[items[1]]} showLegend={false} />);

    expect(screen.getByText("Field check")).toBeInTheDocument();
    expect(screen.queryByText("60-79%: Good")).not.toBeInTheDocument();
  });
});

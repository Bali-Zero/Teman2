import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InfoCard } from "./InfoCard";

describe("InfoCard", () => {
  it("renders the default variant title, content, and optional link", () => {
    render(
      <InfoCard link={{ label: "Read regulation", url: "/rules" }}>
        Entity status is verified against the portal.
      </InfoCard>,
    );

    expect(screen.getByText("Information")).toBeInTheDocument();
    expect(
      screen.getByText("Entity status is verified against the portal."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /read regulation/i })).toHaveAttribute(
      "href",
      "/rules",
    );
  });

  it("uses variant defaults when no explicit title is provided", () => {
    render(
      <div>
        <InfoCard variant="warning">Review manually.</InfoCard>
        <InfoCard variant="success">Ready to submit.</InfoCard>
        <InfoCard variant="error">Submission failed.</InfoCard>
        <InfoCard variant="tip">Use the verified address.</InfoCard>
      </div>,
    );

    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByText("Success")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Pro Tip")).toBeInTheDocument();
  });

  it("supports collapsible content with a custom title and icon", () => {
    render(
      <InfoCard
        title="Internal note"
        icon={<span data-testid="custom-icon">!</span>}
        collapsible
        defaultCollapsed
      >
        Hidden operational detail.
      </InfoCard>,
    );

    expect(screen.getByText("Internal note")).toBeInTheDocument();
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
    expect(screen.queryByText("Hidden operational detail.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Internal note"));

    expect(screen.getByText("Hidden operational detail.")).toBeInTheDocument();
  });
});

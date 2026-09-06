import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DesignSystemFixture } from "./DesignSystemFixture";
import { Button, Card, Container, SectionHeading } from ".";

describe("website design-system primitives", () => {
  it("renders the fixture with native landmarks, headings, cards and actions", () => {
    render(<DesignSystemFixture />);

    expect(
      screen.getByRole("main", { name: "Design system fixture" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Clear decisions, on paper.",
      }),
    ).toHaveAttribute("id", "fixture-title");
    expect(
      screen.getByRole("article", {
        name: "A native, keyboard-ready action group",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask a question" })).toHaveAttribute(
      "type",
      "button",
    );
    expect(screen.getByRole("link", { name: "Review the brief" })).toHaveAttribute(
      "href",
      "#fixture-title",
    );
  });

  it("keeps interactive controls in native keyboard order", async () => {
    const user = userEvent.setup();
    render(<DesignSystemFixture />);

    await user.tab();
    expect(screen.getByRole("button", { name: "Ask a question" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Review the brief" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Read the evidence" })).toHaveFocus();
  });

  it("forwards semantic and accessibility attributes without client state", () => {
    render(
      <Container as="section" aria-labelledby="section-title" width="wide">
        <SectionHeading id="section-title" level={3} title="Service details" />
        <Card as="div" data-testid="quiet-card" tone="quiet">
          <Button aria-describedby="button-note" disabled type="button">
            Continue
          </Button>
          <p id="button-note">Available after review.</p>
        </Card>
      </Container>,
    );

    expect(screen.getByRole("region", { name: "Service details" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3 })).toHaveAttribute(
      "id",
      "section-title",
    );
    expect(screen.getByTestId("quiet-card").tagName).toBe("DIV");
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });
});

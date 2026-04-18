import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BlockedStateCTA } from "./BlockedStateCTA";

describe("BlockedStateCTA", () => {
  it("renders reason text when provided", () => {
    render(<BlockedStateCTA practiceId={42} reason="waiting on notary" />);
    expect(
      screen.getByText(/Practice blocked: waiting on notary\./i),
    ).toBeInTheDocument();
  });

  it("omits reason suffix when null/undefined", () => {
    const { rerender } = render(<BlockedStateCTA practiceId={42} />);
    expect(screen.getByText(/^Practice blocked\.$/i)).toBeInTheDocument();

    rerender(<BlockedStateCTA practiceId={42} reason={null} />);
    expect(screen.getByText(/^Practice blocked\.$/i)).toBeInTheDocument();
  });

  it("encodes practice ID into href (numeric)", () => {
    render(<BlockedStateCTA practiceId={123} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/portal/messages?topic=practice-123");
  });

  it("encodes practice ID into href (string with special chars)", () => {
    render(<BlockedStateCTA practiceId="abc/12 3" />);
    const link = screen.getByRole("link");
    // encodeURIComponent: "/" -> "%2F", " " -> "%20"
    expect(link).toHaveAttribute(
      "href",
      "/portal/messages?topic=practice-abc%2F12%203",
    );
  });

  it("has role=alert on the container", () => {
    render(<BlockedStateCTA practiceId={1} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("renders the contact link text", () => {
    render(<BlockedStateCTA practiceId={1} />);
    expect(screen.getByRole("link")).toHaveTextContent(/Contact the team/i);
  });
});

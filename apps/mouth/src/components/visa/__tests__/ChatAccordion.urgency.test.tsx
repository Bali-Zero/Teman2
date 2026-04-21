import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatAccordion } from "../ChatAccordion";

vi.mock("../VisaChat", () => ({
  VisaChat: () => <div data-testid="visa-chat-mock" />,
}));

describe("ChatAccordion urgency copy", () => {
  it("uses urgent copy when daysRemaining <= 7", () => {
    render(<ChatAccordion checkHash="x" sessionJwt="j" daysRemaining={5} />);
    expect(screen.getByRole("button", { name: /urgent/i })).toBeInTheDocument();
  });

  it("uses short-window copy when 8 <= daysRemaining <= 30", () => {
    render(<ChatAccordion checkHash="x" sessionJwt="j" daysRemaining={20} />);
    expect(screen.getByRole("button", { name: /2 weeks or less/i })).toBeInTheDocument();
  });

  it("uses default copy when daysRemaining > 30 or undefined", () => {
    render(<ChatAccordion checkHash="x" sessionJwt="j" daysRemaining={90} />);
    expect(screen.getByRole("button", { name: /ask 3 free questions/i })).toBeInTheDocument();
  });
});

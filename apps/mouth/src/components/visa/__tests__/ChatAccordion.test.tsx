import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatAccordion } from "../ChatAccordion";

vi.mock("../VisaChat", () => ({
  VisaChat: ({ checkHash, sessionJwt }: { checkHash?: string; sessionJwt?: string }) => (
    <div data-testid="visa-chat-mock" data-hash={checkHash ?? ""} data-jwt={sessionJwt ?? ""} />
  ),
}));

describe("ChatAccordion", () => {
  it("is closed by default and does not mount VisaChat", () => {
    render(<ChatAccordion checkHash="abc" sessionJwt="jwt" />);
    expect(screen.queryByTestId("visa-chat-mock")).toBeNull();
    expect(screen.getByRole("button", { name: /ask 3 free questions/i })).toBeInTheDocument();
  });

  it("opens inline on header click and mounts VisaChat with props", () => {
    render(<ChatAccordion checkHash="abc1234567890000" sessionJwt="tokenXYZ" />);
    fireEvent.click(screen.getByRole("button", { name: /ask 3 free questions/i }));
    const chat = screen.getByTestId("visa-chat-mock");
    expect(chat.dataset.hash).toBe("abc1234567890000");
    expect(chat.dataset.jwt).toBe("tokenXYZ");
  });

  it("renders nothing when sessionJwt is empty", () => {
    const { container } = render(<ChatAccordion checkHash="abc" sessionJwt="" />);
    expect(container).toBeEmptyDOMElement();
  });
});

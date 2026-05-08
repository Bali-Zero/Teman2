import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TerminalToolCall } from "./TerminalToolCall";

describe("TerminalToolCall", () => {
  it("renders running calls without expansion when there are no details", () => {
    render(
      <TerminalToolCall
        toolCall={{
          name: "search_kbli",
          status: "running",
        }}
      />,
    );

    const button = screen.getByRole("button", {
      name: "Tool call search_kbli running",
    });
    expect(button).toBeDisabled();
    expect(screen.getByText("search_kbli")).toBeInTheDocument();
    expect(screen.queryByText("args")).not.toBeInTheDocument();
  });

  it("expands completed calls with args, result, and seconds duration", () => {
    render(
      <TerminalToolCall
        toolCall={{
          name: "pricing_lookup",
          status: "complete",
          duration: 1250,
          args: { service: "PMA", tier: "prime" },
          result: "Rp 10.000.000",
        }}
      />,
    );

    expect(screen.getByText("· 1.3s")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Tool call pricing_lookup complete",
      }),
    );

    expect(screen.getByText("args")).toBeInTheDocument();
    expect(screen.getByText(/"service": "PMA"/)).toBeInTheDocument();
    expect(screen.getByText("result")).toBeInTheDocument();
    expect(screen.getByText("Rp 10.000.000")).toBeInTheDocument();
  });

  it("renders errored calls and millisecond duration", () => {
    render(
      <TerminalToolCall
        toolCall={{
          name: "vault_sync",
          status: "error",
          duration: 400,
          result: "Permission denied",
        }}
      />,
    );

    expect(screen.getByText("· 400ms")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Tool call vault_sync error",
      }),
    );

    expect(screen.getByText("Permission denied")).toBeInTheDocument();
  });
});

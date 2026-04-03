import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ZohoConnectBanner } from "../ZohoConnectBanner";

describe("ZohoConnectBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the connect heading", () => {
    render(<ZohoConnectBanner onConnect={vi.fn()} isConnecting={false} />);
    expect(screen.getByText("Connect your Zoho Mail")).toBeInTheDocument();
  });

  it("renders the connect description", () => {
    render(<ZohoConnectBanner onConnect={vi.fn()} isConnecting={false} />);
    expect(
      screen.getByText(
        /Connect your Zoho Mail account to read, send, and manage emails/,
      ),
    ).toBeInTheDocument();
  });

  it("renders connect button when not connecting", () => {
    render(<ZohoConnectBanner onConnect={vi.fn()} isConnecting={false} />);
    expect(screen.getByText("Connect to Zoho Mail")).toBeInTheDocument();
  });

  it("calls onConnect when button is clicked", () => {
    const onConnect = vi.fn();
    render(<ZohoConnectBanner onConnect={onConnect} isConnecting={false} />);
    fireEvent.click(screen.getByText("Connect to Zoho Mail"));
    expect(onConnect).toHaveBeenCalledTimes(1);
  });

  it("shows connecting state with spinner", () => {
    render(<ZohoConnectBanner onConnect={vi.fn()} isConnecting={true} />);
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
  });

  it("disables button when connecting", () => {
    render(<ZohoConnectBanner onConnect={vi.fn()} isConnecting={true} />);
    const button = screen.getByText("Connecting...").closest("button")!;
    expect(button).toBeDisabled();
  });

  it("renders email icon SVG", () => {
    const { container } = render(
      <ZohoConnectBanner onConnect={vi.fn()} isConnecting={false} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
  });
});

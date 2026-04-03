import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Mock logger before importing the component
vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

// Mock lucide-react
vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) => (
    <svg data-testid="alert-icon" {...props} />
  ),
  RefreshCw: (props: Record<string, unknown>) => (
    <svg data-testid="refresh-icon" {...props} />
  ),
}));

// Import after mocks - use dynamic import alias to avoid name collision
import ErrorPage from "../error";

describe("Drive Error Page", () => {
  const testError = Object.assign(new globalThis.Error("Test error message"), { digest: undefined }) as globalThis.Error & { digest?: string };
  const mockReset = vi.fn();

  it("renders error heading", () => {
    render(<ErrorPage error={testError} reset={mockReset} />);
    expect(screen.getByText("Qualcosa è andato storto")).toBeInTheDocument();
  });

  it("renders error description", () => {
    render(<ErrorPage error={testError} reset={mockReset} />);
    expect(
      screen.getByText(
        "Si è verificato un errore durante il caricamento di Drive. Riprova o torna alla home.",
      ),
    ).toBeInTheDocument();
  });

  it("renders retry button", () => {
    render(<ErrorPage error={testError} reset={mockReset} />);
    expect(screen.getByText("Riprova")).toBeInTheDocument();
  });

  it("calls reset when retry button is clicked", () => {
    render(<ErrorPage error={testError} reset={mockReset} />);
    fireEvent.click(screen.getByText("Riprova"));
    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  it("renders home link", () => {
    render(<ErrorPage error={testError} reset={mockReset} />);
    const homeLink = screen.getByText("Torna alla home");
    expect(homeLink).toBeInTheDocument();
    expect(homeLink.closest("a")).toHaveAttribute(
      "href",
      "https://kita.balizero.com",
    );
  });
});

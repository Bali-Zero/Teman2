import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the canonical core theme context (WS1: migrated off next-themes)
const mockSetTheme = vi.fn();
let mockTheme = "operative-dark";

vi.mock("@balizero/core/components/ThemeProvider", () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    mockTheme = "operative-dark";
    mockSetTheme.mockClear();
  });

  it("renders a toggle button", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", {
      name: /toggle theme|switch to/i,
    });
    expect(button).toBeDefined();
  });

  it("switches from dark to light when clicked", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /switch to light/i });
    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("operative-light");
  });

  it("switches from light to dark when clicked", () => {
    mockTheme = "operative-light";
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /switch to dark/i });
    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("operative-dark");
  });

  it("treats the editorial navy theme as dark", () => {
    mockTheme = "editorial";
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /switch to light/i });
    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("operative-light");
  });

  it("has accessible aria-label", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");
    expect(button.getAttribute("aria-label")).toBeTruthy();
  });
});

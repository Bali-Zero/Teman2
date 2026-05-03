import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock next-themes
const mockSetTheme = vi.fn();
let mockTheme = "dark";

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    mockTheme = "dark";
    mockSetTheme.mockClear();
  });

  it("renders a toggle button", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /toggle theme|switch to/i });
    expect(button).toBeDefined();
  });

  it("switches from dark to light when clicked", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /switch to light/i });
    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });

  it("switches from light to dark when clicked", () => {
    mockTheme = "light";
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /switch to dark/i });
    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it("has accessible aria-label", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");
    expect(button.getAttribute("aria-label")).toBeTruthy();
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const setLanguage = vi.fn();
const useMeMock = vi.fn();

vi.mock("@/hooks/useLanguage", () => ({
  useLanguage: () => ({ language: "en", setLanguage, isSyncing: false }),
}));

vi.mock("@/hooks/useMe", () => ({
  useMe: () => useMeMock(),
}));

import { LanguageSettings } from "./LanguageSettings";

describe("LanguageSettings", () => {
  beforeEach(() => {
    setLanguage.mockReset();
    useMeMock.mockReset();
    useMeMock.mockReturnValue({
      data: {
        id: "u_1",
        email: "zero@balizero.com",
        name: "Zero",
        role: "admin",
        language: "en",
      },
      error: undefined,
      isLoading: false,
    });
  });

  it("renders three language radio buttons", () => {
    render(<LanguageSettings />);
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
    expect(screen.getByLabelText(/Italiano/)).toBeInTheDocument();
    expect(screen.getByLabelText(/English/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Bahasa Indonesia/)).toBeInTheDocument();
  });

  it("calls setLanguage with the selected code on change", () => {
    render(<LanguageSettings />);
    fireEvent.click(screen.getByLabelText(/Italiano/));
    expect(setLanguage).toHaveBeenCalledWith("it");
  });
});

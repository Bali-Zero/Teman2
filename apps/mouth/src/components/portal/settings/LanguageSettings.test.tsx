import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const updatePreferences = vi.fn();
const usePortalPreferencesMock = vi.fn();

vi.mock("@/hooks/usePortal", () => ({
  usePortalPreferences: () => usePortalPreferencesMock(),
}));

import { LanguageSettings } from "./LanguageSettings";

describe("LanguageSettings", () => {
  beforeEach(() => {
    document.cookie = "bz_lang=; Max-Age=0; Path=/";
    updatePreferences.mockReset();
    usePortalPreferencesMock.mockReset();
    usePortalPreferencesMock.mockReturnValue({
      data: {
        emailNotifications: true,
        whatsappNotifications: true,
        language: "en",
        timezone: "Asia/Jakarta",
      },
      error: null,
      isLoading: false,
      isUpdating: false,
      updatePreferences,
    });
  });

  afterEach(() => {
    document.cookie = "bz_lang=; Max-Age=0; Path=/";
  });

  it("renders three language radio buttons", () => {
    render(<LanguageSettings />);
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
    expect(screen.getByLabelText(/Italiano/)).toBeInTheDocument();
    expect(screen.getByLabelText(/English/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Bahasa Indonesia/)).toBeInTheDocument();
  });

  it("reads the persisted portal preference rather than the auth profile", () => {
    usePortalPreferencesMock.mockReturnValue({
      data: {
        emailNotifications: true,
        whatsappNotifications: true,
        language: "it",
        timezone: "Asia/Jakarta",
      },
      error: null,
      isLoading: false,
      isUpdating: false,
      updatePreferences,
    });

    render(<LanguageSettings />);
    expect(screen.getByLabelText(/Italiano/)).toBeChecked();
    expect(screen.getByLabelText(/English/)).not.toBeChecked();
  });

  it("persists a selection before updating the shared cookie", () => {
    updatePreferences.mockImplementation((_update, options) => {
      options.onSuccess();
    });

    render(<LanguageSettings />);
    fireEvent.click(screen.getByLabelText(/Bahasa Indonesia/));

    expect(updatePreferences).toHaveBeenCalledWith(
      { language: "id" },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
    expect(document.cookie).toMatch(/bz_lang=id/);
    expect(screen.getByText("Language preference saved.")).toBeInTheDocument();
  });

  it("rolls back the optimistic selection and shows a save error", () => {
    updatePreferences.mockImplementation((_update, options) => {
      options.onError();
    });

    render(<LanguageSettings />);
    fireEvent.click(screen.getByLabelText(/Italiano/));

    expect(screen.getByLabelText(/English/)).toBeChecked();
    expect(document.cookie).not.toMatch(/bz_lang=it/);
    expect(
      screen.getByText("Unable to save language preference. Please try again."),
    ).toBeInTheDocument();
  });

  it("fails closed when the persisted preference cannot be loaded", () => {
    usePortalPreferencesMock.mockReturnValue({
      data: undefined,
      error: new Error("HTTP 500"),
      isLoading: false,
      isUpdating: false,
      updatePreferences,
    });

    render(<LanguageSettings />);

    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to load language preference.",
    );
  });
});

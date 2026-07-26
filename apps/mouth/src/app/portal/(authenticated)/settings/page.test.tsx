import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/portal/settings/SettingsTabs", () => ({
  SettingsTabs: () => <div data-testid="settings-tabs">tabs</div>,
}));

import SettingsPage from "./page";

describe("SettingsPage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + Cormorant serif in --tx-pure", () => {
    const { container } = render(<SettingsPage />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Settings");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Tab shell still mounts below the masthead.
    expect(screen.getByTestId("settings-tabs")).toBeInTheDocument();

    // Drain guard: no hardcoded hex colors (was text-[#f0ece4]).
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

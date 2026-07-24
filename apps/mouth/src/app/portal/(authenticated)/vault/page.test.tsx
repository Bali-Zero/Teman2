import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/portal/vault/VaultLayout", () => ({
  VaultLayout: () => <div>Client-safe vault</div>,
}));

vi.mock("@/hooks/usePortalDriveFiles", () => ({
  usePortalDriveFiles: () => ({
    data: {
      folders: [{ id: "drive-folder", name: "Internal Drive" }],
      total_files: 7,
    },
    isLoading: false,
  }),
  usePortalDriveSubfolder: () => ({ data: undefined, isLoading: false }),
}));

import VaultPage from "./page";

describe("Portal VaultPage", () => {
  it("does not render Drive navigation for client portal users", () => {
    render(<VaultPage />);

    expect(screen.getByText("Client-safe vault")).toBeInTheDocument();
    expect(screen.queryByText(/Drive Files/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Internal Drive")).not.toBeInTheDocument();
  });

  it("renders the GARUDA Day masthead (copper rule + serif headline)", () => {
    const { container } = render(<VaultPage />);

    // Copper rule + Cormorant serif headline in --tx-pure (WS3 slice 5).
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Document Vault");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Drain guard: no hardcoded hex colors in the page chrome.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

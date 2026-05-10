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
});

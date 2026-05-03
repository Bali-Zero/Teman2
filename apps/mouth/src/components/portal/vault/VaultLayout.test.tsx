import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { VaultFile } from "@/lib/schemas/vault";

// Mock useVaultFiles
const mockMutate = vi.fn();
let mockResult: {
  data: VaultFile[] | undefined;
  error: Error | undefined;
  isLoading: boolean;
  mutate: typeof mockMutate;
} = {
  data: undefined,
  error: undefined,
  isLoading: false,
  mutate: mockMutate,
};

vi.mock("@/hooks/useVaultFiles", () => ({
  useVaultFiles: () => mockResult,
}));

vi.mock("@/hooks/useVaultUpload", () => ({
  useVaultUpload: () => ({
    state: { status: "idle" },
    upload: vi.fn(),
    reset: vi.fn(),
  }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

import { VaultLayout } from "./VaultLayout";

describe("VaultLayout", () => {
  it("renders loading state", () => {
    mockResult = {
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: mockMutate,
    };
    render(<VaultLayout />);
    expect(screen.getByText(/Loading your files/i)).toBeInTheDocument();
  });

  it("renders files when data resolves", () => {
    const files: VaultFile[] = [
      {
        id: 1,
        type: "passport",
        name: "pass.pdf",
        status: "received",
        expiry_date: null,
        size_kb: 100,
        practice_id: null,
        practice_name: null,
        downloadable: false,
        created_at: "2026-04-18T00:00:00Z",
      },
    ];
    mockResult = {
      data: files,
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    };
    render(<VaultLayout />);
    expect(screen.getByText("pass.pdf")).toBeInTheDocument();
  });

  it("renders error with retry when fetch fails", () => {
    mockResult = {
      data: undefined,
      error: new Error("boom"),
      isLoading: false,
      mutate: mockMutate,
    };
    render(<VaultLayout />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /Unable to load vault/i,
    );
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

const mockUpload = vi.fn();
vi.mock("@/hooks/useVaultUpload", () => ({
  useVaultUpload: () => ({
    state: { status: "idle" },
    upload: mockUpload,
    reset: vi.fn(),
  }),
}));

let mockMatters: {
  data:
    | { matters: Array<{ id: number; title: string; status: string }> }
    | undefined;
  isLoading: boolean;
  isError: boolean;
  refetch: () => void;
} = {
  data: { matters: [] },
  isLoading: false,
  isError: false,
  refetch: vi.fn(),
};
vi.mock("@/hooks/usePortal", () => ({
  usePortalMatters: () => mockMatters,
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

  describe("upload practice selection", () => {
    const setMatters = (
      matters: Array<{ id: number; title: string; status: string }>,
    ) => {
      mockResult = {
        data: [],
        error: undefined,
        isLoading: false,
        mutate: mockMutate,
      };
      mockMatters = {
        data: { matters },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      };
      mockUpload.mockReset();
    };
    const pick = () => {
      const input = screen.getByLabelText(
        "Choose file to upload",
      ) as HTMLInputElement;
      const file = new File(["x"], "a.pdf", { type: "application/pdf" });
      Object.defineProperty(input, "files", {
        value: [file],
        configurable: true,
      });
      fireEvent.change(input);
    };

    it("0 active: no picker, uploads without practice", () => {
      setMatters([
        { id: 1, title: "KITAS", status: "completed" },
        { id: 2, title: "PT PMA", status: "cancelled" },
      ]);
      render(<VaultLayout />);
      expect(screen.queryByLabelText(/Upload to practice/i)).toBeNull();
      pick();
      expect(mockUpload.mock.calls[0][1].practiceId).toBeNull();
    });

    it("1 active: visible preselection, changeable", () => {
      setMatters([
        { id: 1, title: "KITAS", status: "completed" },
        { id: 5, title: "PT PMA", status: "on_process" },
      ]);
      render(<VaultLayout />);
      const select = screen.getByLabelText(
        /Upload to practice/i,
      ) as HTMLSelectElement;
      expect(select.value).toBe("5");
      // Client-facing: the practice title only, never the raw internal status.
      expect(
        screen.getByRole("option", { name: "PT PMA" }),
      ).toBeInTheDocument();
      expect(screen.queryByText(/on[_ ]process/i)).toBeNull();
      pick();
      expect(mockUpload.mock.calls[0][1].practiceId).toBe("5");

      fireEvent.change(select, { target: { value: "" } });
      pick();
      expect(mockUpload.mock.calls[1][1].practiceId).toBeNull();
    });

    it("2+ active: blocked until the client chooses", () => {
      setMatters([
        { id: 5, title: "PT PMA", status: "on_process" },
        { id: 6, title: "KITAS", status: "inquiry" },
      ]);
      render(<VaultLayout />);
      const select = screen.getByLabelText(
        /Upload to practice/i,
      ) as HTMLSelectElement;
      expect(select.value).toBe("");
      expect(screen.getByLabelText("Choose file to upload")).toBeDisabled();
      expect(screen.getByText(/Choose a practice above/i)).toBeInTheDocument();

      fireEvent.change(select, { target: { value: "6" } });
      expect(screen.getByLabelText("Choose file to upload")).not.toBeDisabled();
      pick();
      expect(mockUpload.mock.calls[0][1].practiceId).toBe("6");
    });

    it("loading: upload blocked; error: retry shown, upload allowed", () => {
      setMatters([]);
      mockMatters = { ...mockMatters, data: undefined, isLoading: true };
      const { unmount } = render(<VaultLayout />);
      expect(screen.getByLabelText("Choose file to upload")).toBeDisabled();
      unmount();

      mockMatters = { ...mockMatters, isLoading: false, isError: true };
      render(<VaultLayout />);
      expect(
        screen.getByText(/couldn.t load your practices/i),
      ).toBeInTheDocument();
      expect(screen.getByLabelText("Choose file to upload")).not.toBeDisabled();
    });
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VaultFileGrid } from "./VaultFileGrid";
import type { VaultFile } from "@/lib/schemas/vault";

function makeFile(overrides: Partial<VaultFile> = {}): VaultFile {
  return {
    id: 1,
    type: "passport",
    name: "file.pdf",
    status: "received",
    expiry_date: null,
    size_kb: 100,
    practice_id: null,
    practice_name: null,
    downloadable: false,
    created_at: "2026-04-18T00:00:00Z",
    ...overrides,
  };
}

describe("VaultFileGrid", () => {
  it("shows empty state when no files", () => {
    render(<VaultFileGrid files={[]} />);
    expect(screen.getByText(/No files in this view/i)).toBeInTheDocument();
  });

  it("renders one <li> per file", () => {
    const files = [
      makeFile({ id: 1, name: "a.pdf" }),
      makeFile({ id: 2, name: "b.pdf" }),
      makeFile({ id: 3, name: "c.pdf" }),
    ];
    render(<VaultFileGrid files={files} />);
    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.pdf")).toBeInTheDocument();
    expect(screen.getByText("c.pdf")).toBeInTheDocument();
  });

  it("omits Download button when file is not downloadable", () => {
    const files = [makeFile({ downloadable: false })];
    render(<VaultFileGrid files={files} onDownload={() => {}} />);
    expect(
      screen.queryByRole("button", { name: /download/i }),
    ).not.toBeInTheDocument();
  });

  it("fires onDownload with file when Download clicked", () => {
    const onDownload = vi.fn();
    const file = makeFile({ id: 42, downloadable: true });
    render(<VaultFileGrid files={[file]} onDownload={onDownload} />);
    fireEvent.click(screen.getByRole("button", { name: /download/i }));
    expect(onDownload).toHaveBeenCalledTimes(1);
    expect(onDownload).toHaveBeenCalledWith(file);
  });
});

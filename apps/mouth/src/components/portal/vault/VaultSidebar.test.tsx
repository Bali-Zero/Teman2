import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VaultSidebar } from "./VaultSidebar";
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

describe("VaultSidebar", () => {
  it("lists unique practices from files", () => {
    const files: VaultFile[] = [
      makeFile({ id: 1, practice_id: 10, practice_name: "P-10" }),
      makeFile({ id: 2, practice_id: 10, practice_name: "P-10" }),
      makeFile({ id: 3, practice_id: 20, practice_name: "P-20" }),
    ];
    render(
      <VaultSidebar
        files={files}
        practiceFilter={null}
        typeFilter={null}
        onPracticeChange={() => {}}
        onTypeChange={() => {}}
      />,
    );
    expect(screen.getByText(/P-10/)).toBeInTheDocument();
    expect(screen.getByText(/P-20/)).toBeInTheDocument();
  });

  it("shows correct counts per practice and type", () => {
    const files: VaultFile[] = [
      makeFile({
        id: 1,
        type: "passport",
        practice_id: 10,
        practice_name: "P-10",
      }),
      makeFile({
        id: 2,
        type: "passport",
        practice_id: 10,
        practice_name: "P-10",
      }),
      makeFile({ id: 3, type: "visa", practice_id: 20, practice_name: "P-20" }),
    ];
    render(
      <VaultSidebar
        files={files}
        practiceFilter={null}
        typeFilter={null}
        onPracticeChange={() => {}}
        onTypeChange={() => {}}
      />,
    );
    // All (3), P-10 (2), P-20 (1), passport (2), visa (1)
    expect(screen.getByText(/All/)).toBeInTheDocument();
    expect(screen.getAllByText(/\(2\)/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/\(1\)/).length).toBeGreaterThanOrEqual(1);
  });

  it("clicking a practice fires onPracticeChange with id", () => {
    const onPracticeChange = vi.fn();
    const files: VaultFile[] = [
      makeFile({ id: 1, practice_id: 10, practice_name: "P-10" }),
    ];
    render(
      <VaultSidebar
        files={files}
        practiceFilter={null}
        typeFilter={null}
        onPracticeChange={onPracticeChange}
        onTypeChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByText(/P-10/));
    expect(onPracticeChange).toHaveBeenCalledWith("10");
  });

  it("hides types section when files have no types", () => {
    // If all types are empty strings they'll be filtered out
    render(
      <VaultSidebar
        files={[]}
        practiceFilter={null}
        typeFilter={null}
        onPracticeChange={() => {}}
        onTypeChange={() => {}}
      />,
    );
    expect(screen.queryByText(/^Types$/)).not.toBeInTheDocument();
  });
});

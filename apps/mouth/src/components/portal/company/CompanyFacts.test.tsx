import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { FactBoxes } from "./FactBoxes";
import { IdentityRow } from "./IdentityRow";
import { StatusChip } from "./StatusChip";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

describe("portal company summary components", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(navigator.clipboard.writeText).mockResolvedValue(undefined);
  });

  it("renders status chip variants with optional icon", () => {
    render(<StatusChip label="Active" variant="amber" icon={<span>!</span>} />);

    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("!")).toBeInTheDocument();
  });

  it("renders identity values and copies identifiers to the clipboard", () => {
    render(
      <IdentityRow
        nib="1234567890123"
        npwp="01.234.567.8-901.000"
        companyType="PT PMA"
      />,
    );

    expect(screen.getByText("Nomor Induk Berusaha")).toBeInTheDocument();
    expect(screen.getByText("Tax Identification Number")).toBeInTheDocument();
    expect(screen.getByText("Penanaman Modal Asing")).toBeInTheDocument();

    fireEvent.click(screen.getByText("1234567890123"));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("1234567890123");
    expect(toast.success).toHaveBeenCalledWith("Copied");
  });

  it("renders empty identity cells only when at least one field is present", () => {
    const { container, rerender } = render(
      <IdentityRow companyType="" nib="" npwp="" />,
    );
    expect(container).toBeEmptyDOMElement();

    rerender(<IdentityRow companyType="Custom Foundation" />);
    expect(screen.getByText("Custom Foundation")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("renders fact boxes with capital, age, akta metadata, and vault count", () => {
    render(
      <FactBoxes
        capital="Rp 10B"
        aktaPerubahanNo="22"
        aktaPerubahanDate="2025-06-01"
        foundingDate="2024-01-15"
        documentCount={7}
      />,
    );

    expect(screen.getByText("Rp 10B")).toBeInTheDocument();
    expect(screen.getByText("Post-Akta #22, 2025")).toBeInTheDocument();
    expect(screen.getByText("Company Age")).toBeInTheDocument();
    expect(screen.getByText("Incorporated January 15, 2024")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Legal vault, Drive-synced")).toBeInTheDocument();
  });

  it("renders fallback fact values when optional details are missing", () => {
    render(<FactBoxes capital={null} documentCount={0} />);

    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});

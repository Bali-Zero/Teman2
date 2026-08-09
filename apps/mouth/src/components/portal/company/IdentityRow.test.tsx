import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IdentityRow } from "./IdentityRow";

const mocks = vi.hoisted(() => ({
  writeText: vi.fn<(_: string) => Promise<void>>(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: mocks.toastSuccess },
}));

describe("IdentityRow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.writeText.mockResolvedValue();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: mocks.writeText },
    });
  });

  it("exposes NIB and NPWP copy actions as named keyboard buttons", () => {
    render(
      <IdentityRow
        nib="synthetic-nib"
        npwp="synthetic-npwp"
        companyType="PT PMA"
      />,
    );

    const copyNib = screen.getByRole("button", { name: "Copy NIB" });
    const copyNpwp = screen.getByRole("button", { name: "Copy NPWP" });

    expect(copyNib.tagName).toBe("BUTTON");
    expect(copyNib).toHaveAttribute("type", "button");
    expect(copyNpwp.tagName).toBe("BUTTON");
    expect(copyNpwp).toHaveAttribute("type", "button");

    fireEvent.click(copyNib);
    fireEvent.click(copyNpwp);

    expect(mocks.writeText).toHaveBeenNthCalledWith(1, "synthetic-nib");
    expect(mocks.writeText).toHaveBeenNthCalledWith(2, "synthetic-npwp");
    expect(mocks.toastSuccess).toHaveBeenCalledTimes(2);
  });

  it("does not expose copy actions for missing identifiers", () => {
    render(<IdentityRow companyType="PT PMA" />);

    expect(screen.queryByRole("button", { name: /copy/i })).toBeNull();
  });
});

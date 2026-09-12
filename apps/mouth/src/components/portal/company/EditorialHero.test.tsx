import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EditorialHero } from "./EditorialHero";

const baseProps = {
  companyName: "Synthetic Example Enterprises",
  companyType: "PT PMA",
  companyStatus: "active",
  nib: "1234567890123",
  kbliDescription: "Wholesale trade of synthetic goods",
  city: "Denpasar",
  province: "Bali",
  addressStr: "Jl. Synthetic No. 1",
  capital: "IDR 10,000,000,000",
  shareholderCount: 2,
  foundingYear: 2021,
  companyId: 42,
};

describe("EditorialHero", () => {
  it("pins the read-only portal rendering: no companyId/onEdit affordance means no edit control", () => {
    render(
      <EditorialHero {...baseProps} companyId={undefined} onEdit={undefined} />,
    );

    expect(screen.getByText("Synthetic Example Enterprises")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit company" })).toBeNull();
  });

  it("renders the CRM's additive editable affordance when onEdit is supplied (companyId present)", () => {
    const onEdit = vi.fn();
    render(<EditorialHero {...baseProps} onEdit={onEdit} />);

    const editButton = screen.getByRole("button", { name: "Edit company" });
    expect(editButton).toBeTruthy();

    fireEvent.click(editButton);
    expect(onEdit).toHaveBeenCalledTimes(1);
  });
});

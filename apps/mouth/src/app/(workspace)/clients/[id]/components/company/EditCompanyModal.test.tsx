import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditCompanyModal } from "./EditCompanyModal";

// --- module mocks -----------------------------------------------------------
const { updateCompany } = vi.hoisted(() => ({
  updateCompany: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    crm: { updateCompany },
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

/** The `updates` object (2nd positional arg) sent to api.crm.updateCompany. */
function lastUpdatePayload(): Record<string, unknown> {
  const calls = updateCompany.mock.calls;
  const call = calls[calls.length - 1];
  return (call?.[1] ?? {}) as Record<string, unknown>;
}

async function clickSave(): Promise<void> {
  await userEvent.click(screen.getByRole("button", { name: /save changes/i }));
}

describe("EditCompanyModal — dirty-fields payload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateCompany.mockResolvedValue({
      id: 1,
      company_name: "x",
      message: "ok",
    });
  });

  it("sends only the field the user changed", async () => {
    render(
      <EditCompanyModal
        companyId={1}
        initialData={{
          company_name: "PT Bali Investment Mandiri",
          company_type: "PT PMA",
          city: "Denpasar",
        }}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    const cityInput = screen.getByDisplayValue("Denpasar");
    await userEvent.clear(cityInput);
    await userEvent.type(cityInput, "Ubud");
    await clickSave();

    await waitFor(() => expect(updateCompany).toHaveBeenCalled());
    expect(lastUpdatePayload()).toEqual({ city: "Ubud" });
  });

  it("closes without an API call when nothing changed", async () => {
    const onClose = vi.fn();
    render(
      <EditCompanyModal
        companyId={1}
        initialData={{ company_name: "PT Bali Investment Mandiri" }}
        onClose={onClose}
        onSave={vi.fn()}
      />,
    );

    await clickSave();

    expect(updateCompany).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("sends null (not an empty string) for a cleared date field", async () => {
    render(
      <EditCompanyModal
        companyId={1}
        initialData={{
          company_name: "PT Bali Investment Mandiri",
          akta_pendirian_date: "2020-01-15",
        }}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    await userEvent.clear(screen.getByDisplayValue("2020-01-15"));
    await clickSave();

    await waitFor(() => expect(updateCompany).toHaveBeenCalled());
    expect(lastUpdatePayload()).toEqual({ akta_pendirian_date: null });
  });
});

describe("EditCompanyModal — company_type mapping", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateCompany.mockResolvedValue({
      id: 1,
      company_name: "x",
      message: "ok",
    });
  });

  it("maps a legacy stored value to its canonical option instead of defaulting silently", () => {
    render(
      <EditCompanyModal
        companyId={1}
        initialData={{ company_name: "Test Co", company_type: "PMA" }}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    const select = screen.getByDisplayValue("PT PMA") as HTMLSelectElement;
    expect(select.value).toBe("PT PMA");
  });

  it("shows an unrecognized stored value as its own selected option, never the first option", () => {
    render(
      <EditCompanyModal
        companyId={1}
        initialData={{ company_name: "Test Co", company_type: "Yayasan" }}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    // The Type select renders before the Status select in the DOM.
    const [typeSelect] = screen.getAllByRole("combobox") as HTMLSelectElement[];
    // The canonical list's first option is "PT PMA" — an unmapped value must
    // never silently resolve to it.
    expect(typeSelect.value).toBe("Yayasan");
  });

  it("does not resend company_type when it was only normalized, not changed by the user", async () => {
    render(
      <EditCompanyModal
        companyId={1}
        initialData={{ company_name: "Test Co", company_type: "PMA" }}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    await clickSave();

    expect(updateCompany).not.toHaveBeenCalled();
  });
});

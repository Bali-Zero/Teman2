import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MyTaxCalendar } from "./MyTaxCalendar";

const sampleResponse = {
  obligations: [
    {
      authority: "Directorate General of Taxes",
      frequency: "Monthly",
      id: "monthly-pph",
      legal_source: "Cleared tax-register source",
      name: "Monthly filing",
      reviewed_on: "2026-09-20",
      upcoming_due_dates: [
        { due_date: "2026-10-01", period_key: "September 2026" },
        { due_date: "2026-11-01", period_key: "October 2026" },
      ],
    },
  ],
  withheld_count: 3,
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

async function chooseCompanyProfile() {
  fireEvent.click(screen.getByLabelText("Company"));
  fireEvent.click(screen.getByLabelText("PT PMA"));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.click(
    screen.getByLabelText("No", { selector: 'input[name="employees"]' }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.click(
    screen.getByLabelText("No", { selector: 'input[name="pkp"]' }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.click(
    screen.getByLabelText("No", { selector: 'input[name="online"]' }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.click(screen.getByLabelText("Construction or pre-operational"));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

describe("MyTaxCalendar", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("posts only the individual taxpayer body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ obligations: [], withheld_count: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MyTaxCalendar />);

    fireEvent.click(screen.getByLabelText("Individual"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      taxpayer_type: "individual",
    });
  });

  it("posts the complete company body with safe false defaults", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ obligations: [], withheld_count: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MyTaxCalendar />);

    await chooseCompanyProfile();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      company_type: "PT_PMA",
      employee_count: 0,
      fiscal_year_end: "12-31",
      has_employees: false,
      has_foreign_employees: false,
      horizon_days: 365,
      investment_stage: "construction",
      pkp: false,
      pmse_vat_appointed: false,
      pse_registered: false,
      serves_indonesian_users_online: false,
      taxpayer_type: "company",
    });
  });

  it("renders reviewed obligations and days on the Makassar civil date", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-29T00:00:00.000Z"));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(sampleResponse)),
    );
    render(<MyTaxCalendar />);

    fireEvent.click(screen.getByLabelText("Individual"));
    await vi.runAllTimersAsync();

    expect(screen.getByText("Monthly filing")).toBeInTheDocument();
    expect(screen.getByText("2026-10-01 · in 2d")).toBeInTheDocument();
    expect(screen.getByText("2026-11-01 — October 2026")).toBeInTheDocument();
    expect(
      screen.getByText("Reviewed by our tax team on 2026-09-20"),
    ).toBeInTheDocument();
  });

  it("shows withheld and both honest empty states", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(sampleResponse))
      .mockResolvedValueOnce(
        jsonResponse({ obligations: [], withheld_count: 0 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ obligations: [], withheld_count: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    expect(
      await screen.findByText(/3 more obligations may apply/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ask our tax team on WhatsApp" }),
    ).toHaveAttribute(
      "href",
      "https://wa.me/628213454721?text=Bali%20Zero%20tax%20calendar",
    );
    unmount();

    render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    expect(
      await screen.findByText(
        "Personal tax deadlines are not in this calendar yet.",
      ),
    ).toBeInTheDocument();
    unmount();

    render(<MyTaxCalendar />);
    await chooseCompanyProfile();
    expect(
      await screen.findByText(
        "None of the obligations in our register apply to this profile.",
      ),
    ).toBeInTheDocument();
  });

  it("handles rate limits and generic errors with retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({}, 429))
      .mockResolvedValueOnce(jsonResponse({}, 500))
      .mockResolvedValueOnce(
        jsonResponse({ obligations: [], withheld_count: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    expect(
      await screen.findByText("Too many requests — try again in a minute."),
    ).toBeInTheDocument();
    unmount();

    render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    expect(
      await screen.findByText(
        "We could not load your calendar. Please try again.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByText(
        "Personal tax deadlines are not in this calendar yet.",
      ),
    ).toBeInTheDocument();
  });

  it("never renders a price currency marker", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(sampleResponse)),
    );
    const { container } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    await screen.findByText("Monthly filing");
    expect(container.textContent).not.toMatch(/Rp|IDR/);
  });
});

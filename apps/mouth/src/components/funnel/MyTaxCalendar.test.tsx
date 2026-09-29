import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MyTaxCalendar } from "./MyTaxCalendar";

const sampleResponse = {
  obligations: [
    {
      authority: "Directorate General of Taxes",
      frequency: "Monthly",
      id: "monthly-pph",
      name: "Monthly filing",
      reviewed_on: "2026-09-20",
      upcoming_due_dates: [
        { due_date: "2026-10-01", period_key: "2026-09" },
        { due_date: "2026-11-01", period_key: "2026-10" },
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
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-09-29T00:00:00.000Z"));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(sampleResponse)),
    );
    render(<MyTaxCalendar />);

    fireEvent.click(screen.getByLabelText("Individual"));

    expect(await screen.findByText("Monthly filing")).toBeInTheDocument();
    expect(screen.getByText("2026-10-01 · in 2d")).toBeInTheDocument();
    expect(screen.getByText("2026-11-01 — 2026-10")).toBeInTheDocument();
    expect(screen.getByText("Reviewed on 2026-09-20")).toBeInTheDocument();
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

  it("never claims nothing applies while rules are only withheld", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ obligations: [], withheld_count: 4 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MyTaxCalendar />);

    await chooseCompanyProfile();

    expect(
      await screen.findByText(/4 more obligations may apply/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/None of the obligations in our register apply/),
    ).not.toBeInTheDocument();
  });

  it("sends the employee count as a non-negative integer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ obligations: [], withheld_count: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Company"));
    fireEvent.click(screen.getByLabelText("PT PMA"));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      screen.getByLabelText("Yes", { selector: 'input[name="employees"]' }),
    );
    fireEvent.click(
      screen.getByLabelText("No", {
        selector: 'input[name="foreign-employees"]',
      }),
    );
    const input = screen.getByLabelText("How many employees?");
    const next = screen.getByRole("button", { name: "Continue" });

    fireEvent.change(input, { target: { value: "" } });
    expect(next).toBeDisabled();
    fireEvent.change(input, { target: { value: "-3" } });
    expect(input).toHaveValue(0);
    fireEvent.change(input, { target: { value: "2.7" } });
    expect(input).toHaveValue(2);
    fireEvent.click(next);
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

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.employee_count).toBe(2);
    expect(Number.isInteger(body.employee_count)).toBe(true);
  });

  it("keeps the WhatsApp link at the 44px touch-target minimum", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(sampleResponse)),
    );
    render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));

    const link = await screen.findByRole("link", {
      name: "Ask our tax team on WhatsApp",
    });

    expect(link.style.minHeight).toBe("44px");
  });

  it("labels provisional dates and explains them once", async () => {
    const response = {
      obligations: [
        {
          ...sampleResponse.obligations[0],
          upcoming_due_dates: [
            {
              due_date: "2026-11-16",
              period_key: "2026-10",
              provisional: false,
            },
            {
              due_date: "2026-12-15",
              period_key: "2026-11",
              provisional: false,
            },
            {
              due_date: "2027-01-04",
              period_key: "2026-12",
              provisional: true,
            },
            { due_date: "2027-04-30", period_key: "FY2026", provisional: true },
            {
              due_date: "2027-06-30",
              period_key: "2026-Q4",
              provisional: true,
            },
          ],
        },
      ],
      withheld_count: 0,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(response)));
    const { container } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));

    await screen.findByText("Monthly filing");

    expect(screen.getAllByText("provisional")).toHaveLength(3);
    const row = screen.getByText("2027-01-04 — 2026-12").closest("li");
    expect(row?.textContent).toContain("2026-12 provisional");
    expect(row?.textContent).not.toContain("2026-12provisional");
    expect(screen.getByText("2027-01-04 — 2026-12").style.whiteSpace).toBe(
      "nowrap",
    );
    expect(container.textContent).toContain("2027-04-30 — FY2026 provisional");
    expect(container.textContent).toContain("2027-06-30 — 2026-Q4 provisional");
    expect(
      screen.getAllByText(/Provisional dates may move to the next working day/),
    ).toHaveLength(1);
  });

  it("shows neither label nor note when no date is provisional", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(sampleResponse)),
    );
    render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));

    await screen.findByText("Monthly filing");

    expect(screen.queryByText("provisional")).not.toBeInTheDocument();
    expect(screen.queryByText(/Provisional dates may move/)).toBeNull();
  });

  it("renders a card without dates as event-driven, with no badge", async () => {
    const response = {
      obligations: [
        {
          ...sampleResponse.obligations[0],
          frequency: "event",
          name: "Event filing",
          upcoming_due_dates: [],
        },
      ],
      withheld_count: 0,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(response)));
    const { container } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));

    await screen.findByText("Event filing");

    expect(
      screen.getByText(
        "No fixed date — due when the triggering event happens.",
      ),
    ).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/NaN|Invalid Date|in \d+d/);
  });

  it("never renders legal_source, even if a payload still carries it", async () => {
    const response = {
      obligations: [
        {
          ...sampleResponse.obligations[0],
          legal_source: "INTERNAL-VERIFICATION-NOTE the PMK PDF is a scan",
        },
      ],
      withheld_count: 0,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(response)));
    const { container } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));

    await screen.findByText("Monthly filing");

    expect(container.textContent).not.toContain("INTERNAL-VERIFICATION-NOTE");
  });

  it("shows human frequency labels and falls back to the raw value", async () => {
    const base = sampleResponse.obligations[0];
    const response = {
      obligations: [
        ["monthly", "a"],
        ["annual", "b"],
        ["one_time", "c"],
        ["event", "d"],
        ["fortnightly", "e"],
      ].map(([frequency, id]) => ({
        ...base,
        frequency,
        id,
        name: `Rule ${id}`,
      })),
      withheld_count: 0,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(response)));
    const { container } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));

    await screen.findByText("Rule a");
    const text = container.textContent ?? "";

    expect(text).toContain("Directorate General of Taxes · Monthly");
    expect(text).toContain("· Annual");
    expect(text).toContain("· One-time");
    expect(text).toContain("· When an event happens");
    expect(text).toContain("· fortnightly");
    expect(text).not.toMatch(/one_time|· event/);
  });

  it("pluralises the withheld note", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ obligations: [], withheld_count: 1 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ obligations: [], withheld_count: 2 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    expect(
      await screen.findByText(/^1 more obligation may apply to you\./),
    ).toBeInTheDocument();
    unmount();

    render(<MyTaxCalendar />);
    fireEvent.click(screen.getByLabelText("Individual"));
    expect(
      await screen.findByText(/^2 more obligations may apply to you\./),
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

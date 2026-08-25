import { render, screen, waitFor } from "@testing-library/react";
import VoaResultPage from "./page";

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function renderWithHash(hash = "opaque-test-hash") {
  return render(<VoaResultPage params={Promise.resolve({ hash })} />);
}

describe("VoaResultPage — DECLINE (owner decision 5, constraint 5b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    fetchMock.mockReset();
  });

  it("shows the empty stamp, never AppStampReveal's ink stamp, on DECLINE", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        verdict: "DECLINE",
        reason_codes: ["PURPOSE_NOT_ELIGIBLE"],
      }),
    });
    window.localStorage.setItem(
      "bz.garuda_voa.wizard",
      JSON.stringify({
        values: {
          case_type: "issuance",
          purpose: "business-meeting",
          trip: { nationality: "USA" },
        },
      }),
    );

    renderWithHash();

    await waitFor(() =>
      expect(screen.getByTestId("bz-empty-stamp")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("bz-stamp")).not.toBeInTheDocument();
    // The mirror line reflects the customer's own submitted purpose.
    expect(screen.getByText(/business meeting/i)).toBeInTheDocument();
    // Routes, never decides: no checkout, no visa product name invented here.
    expect(
      screen.getByRole("link", { name: /Try Visa Match/i }),
    ).toHaveAttribute("href", "/visa/match");
    expect(screen.getByRole("link", { name: /WhatsApp/i })).toBeInTheDocument();
  });

  it("never shows a price or checkout action on DECLINE", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ verdict: "DECLINE", reason_codes: ["GROUP_CASE"] }),
    });
    renderWithHash();

    await waitFor(() =>
      expect(screen.getByTestId("bz-empty-stamp")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Rp\s?\d/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /pay|checkout/i }),
    ).not.toBeInTheDocument();
  });
});

describe("VoaResultPage — ACCEPT", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock.mockReset();
  });

  it("shows the ink stamp with the all-inclusive price, never the empty stamp", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
        published_filing_deadline: "2026-09-08",
      }),
    });
    renderWithHash();

    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("bz-empty-stamp")).not.toBeInTheDocument();
    expect(screen.getByTestId("bz-stamp")).toHaveTextContent(/790/);
    expect(screen.getByText(/Ngurah Rai/i)).toBeInTheDocument();
    // Magic-link email capture is present on the accepted path.
    expect(screen.getByLabelText(/continue by email/i)).toBeInTheDocument();
  });

  it("never renders a fee/PNBP split — one all-inclusive figure only", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
      }),
    });
    renderWithHash();

    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/PNBP/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\+\s?fee/i)).not.toBeInTheDocument();
  });
});

describe("VoaResultPage — result not found", () => {
  it("shows a recovery path, not a raw stack trace, on 404", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404 });
    renderWithHash();

    await waitFor(() =>
      expect(screen.getByText(/couldn't find this check/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: /Start again/i })).toHaveAttribute(
      "href",
      "/visa/voa",
    );
  });
});

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VoaResultPage from "./page";

// The tracker's own emitFunnelAppEvent posts through the SAME global fetch
// mock the tests below use for the eligibility-check/lead-capture/magic-link
// calls — mocked here (mirroring visa/match's page.test.tsx) so it never
// silently consumes a mockResolvedValueOnce meant for a real endpoint, and
// so tracker calls are assertable.
const trackerMocks = vi.hoisted(() => ({
  resultViewed: vi.fn(),
  ctaClicked: vi.fn(),
  whatsappHandoff: vi.fn(),
  shareClicked: vi.fn(),
  emailSubscribed: vi.fn(),
  formSubmitFailed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => ({
      viewed: vi.fn(),
      resultViewed: trackerMocks.resultViewed,
      ctaClicked: trackerMocks.ctaClicked,
      whatsappHandoff: trackerMocks.whatsappHandoff,
      shareClicked: trackerMocks.shareClicked,
      emailSubscribed: trackerMocks.emailSubscribed,
      formSubmitFailed: trackerMocks.formSubmitFailed,
    }),
  };
});

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

  it("tracks resultViewed and the DECLINE-path CTAs, never a form value", async () => {
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
    renderWithHash("opaque-decline-hash");

    await waitFor(() =>
      expect(trackerMocks.resultViewed).toHaveBeenCalledWith(
        "opaque-decline-hash",
      ),
    );

    fireEvent.click(screen.getByRole("link", { name: /Try Visa Match/i }));
    expect(trackerMocks.ctaClicked).toHaveBeenCalledWith(
      "try_visa_match",
      "/visa/match",
    );
    // Law 2: the CTA event carries a label + destination only.
    const wire = JSON.stringify(trackerMocks.ctaClicked.mock.calls);
    expect(wire).not.toContain("USA");
    expect(wire).not.toContain("business-meeting");
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
    expect(trackerMocks.resultViewed).toHaveBeenCalledWith("opaque-test-hash");
  });

  it("copying the share link fires shareClicked('copy'), never the applicant's data", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: /copy link/i }));
    await waitFor(() =>
      expect(trackerMocks.shareClicked).toHaveBeenCalledWith("copy"),
    );
  });

  it("magic-link request fires emailSubscribed on 202, never the email address", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
      }),
    });
    fetchMock.mockResolvedValueOnce({ status: 202 });
    renderWithHash();
    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(/continue by email/i),
      "customer@example.com",
    );
    await user.click(screen.getByRole("button", { name: /email me a link/i }));

    await waitFor(() =>
      expect(trackerMocks.emailSubscribed).toHaveBeenCalledWith(
        "voa_magic_link_request",
      ),
    );
    // Positive control: prove the detector below is not vacuously true — it
    // WOULD catch the email if it were present (it isn't, by construction).
    expect(JSON.stringify(["customer@example.com"])).toContain(
      "customer@example.com",
    );
    const wire = JSON.stringify(trackerMocks.emailSubscribed.mock.calls);
    expect(wire).not.toContain("customer@example.com");
    expect(wire).not.toContain("@example.com");
  });

  it("magic-link request failure fires formSubmitFailed with endpoint + status, never the email", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
      }),
    });
    fetchMock.mockResolvedValueOnce({ status: 500 });
    renderWithHash();
    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(/continue by email/i),
      "customer@example.com",
    );
    await user.click(screen.getByRole("button", { name: /email me a link/i }));

    await waitFor(() =>
      expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
        "/api/visa/voa/auth/magic-links",
        500,
      ),
    );
    const wire = JSON.stringify(trackerMocks.formSubmitFailed.mock.calls);
    expect(wire).not.toContain("customer@example.com");
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

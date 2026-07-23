import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import VisaClockPage from "./page";

/**
 * W0b telemetry regression guard (2026-07-23): same silent-death pattern
 * as visa/match — submit failure was swallowed into `setError` with no
 * event. Failure telemetry carries endpoint + status only, never the
 * visa type / entry date (Law 2).
 */

const trackerMocks = vi.hoisted(() => ({
  formStarted: vi.fn(),
  formSubmitted: vi.fn(),
  formSubmitFailed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => ({
      viewed: vi.fn(),
      formStarted: trackerMocks.formStarted,
      formSubmitted: trackerMocks.formSubmitted,
      formSubmitFailed: trackerMocks.formSubmitFailed,
    }),
  };
});

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText("Entry date"), {
    target: { value: "2026-07-01" },
  });
  fireEvent.change(screen.getByLabelText("Visa type"), {
    target: { value: "B1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Show my timeline" }));
}

describe("VisaClockPage — submit telemetry (W0b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock.mockReset();
  });

  it("HTTP error fires app_form_submit_failed with status, payload-free", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503 });
    render(<VisaClockPage />);
    fillAndSubmit();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not build your timeline/i,
      ),
    );
    expect(trackerMocks.formSubmitted).toHaveBeenCalledWith([
      "visa_type",
      "entry_date",
    ]);
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledTimes(1);
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/clock",
      503,
    );
    // Law 2: no form values in the failure event.
    const emitted = JSON.stringify(trackerMocks.formSubmitFailed.mock.calls);
    expect(emitted).not.toContain("2026-07-01");
    expect(emitted).not.toContain("B1");
  });

  it("network failure (fetch rejects) fires the event with status null", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    render(<VisaClockPage />);
    fillAndSubmit();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/clock",
      null,
    );
  });

  it("2xx with an unparseable body reports the HTTP status, not null", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("Unexpected token");
      },
    });
    render(<VisaClockPage />);
    fillAndSubmit();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/clock",
      200,
    );
  });

  it("successful submit fires no failure event", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ hash: "xyz789" }),
    });
    render(<VisaClockPage />);
    fillAndSubmit();

    await waitFor(() => expect(trackerMocks.formSubmitted).toHaveBeenCalled());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(trackerMocks.formSubmitFailed).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

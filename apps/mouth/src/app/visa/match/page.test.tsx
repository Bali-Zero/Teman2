import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import VisaMatchPage from "./page";

/**
 * W0b telemetry regression guard (2026-07-23): the v1 visa funnel died
 * silently for 3 months because submit failure was swallowed into
 * `setSubmitError` with no event — wizard-starts vs successful submissions
 * were unmeasurable. These tests pin: attempt fires `formSubmitted`,
 * failure fires `formSubmitFailed(endpoint, status)` — and the failure
 * event NEVER carries form values (Law 2: no nationality/purpose/budget
 * in analytics).
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
      wizardStep: vi.fn(),
      wizardAbandoned: vi.fn(),
    }),
  };
});

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

/** Drive the real AppWizard through all 4 steps to the submit. */
function completeWizard() {
  fireEvent.change(screen.getByLabelText("Nationality"), {
    target: { value: "ITA" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.click(
    screen.getByRole("button", {
      name: "Work remotely for a foreign employer",
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  // Duration has no validation gate — default 6 months stands.
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.click(screen.getByRole("button", { name: "Under IDR 50M" }));
  fireEvent.click(screen.getByRole("button", { name: "See result" }));
}

describe("VisaMatchPage — submit telemetry (W0b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    fetchMock.mockReset();
  });

  it("HTTP error fires app_form_submit_failed with status, payload-free", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500 });
    render(<VisaMatchPage />);
    completeWizard();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /could not compute a recommendation/i,
      ),
    );
    expect(trackerMocks.formSubmitted).toHaveBeenCalledWith([
      "nationality",
      "purpose",
      "budget",
    ]);
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledTimes(1);
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/match",
      500,
    );
    // Law 2: the failure event must not become a PII channel.
    const emitted = JSON.stringify(trackerMocks.formSubmitFailed.mock.calls);
    expect(emitted).not.toContain("ITA");
    expect(emitted).not.toContain("work_remote");
    expect(emitted).not.toContain("under_50m");
  });

  it("network failure (fetch rejects) fires the event with status null", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    render(<VisaMatchPage />);
    completeWizard();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/match",
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
    render(<VisaMatchPage />);
    completeWizard();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/match",
      200,
    );
  });

  it("successful submit fires no failure event and no error UI", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ hash: "abc123" }),
    });
    render(<VisaMatchPage />);
    completeWizard();

    await waitFor(() => expect(trackerMocks.formSubmitted).toHaveBeenCalled());
    // Let the router.push microtask flush.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(trackerMocks.formSubmitFailed).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

import {
  act,
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import VoaEligibilityPage from "./page";

/**
 * Bite-proof: the wizard's payload must match `EligibilityCheckRequest`
 * (products/garuda-voa/contracts/openapi.yaml) field-for-field, including
 * the case_type-conditional voa_expiry_date/extension_already_used pair the
 * contract's `allOf` forbids on issuance.
 */

// The tracker's own emitFunnelAppEvent posts to /api/analytics/funnel-event
// through the SAME global fetch mock the tests below use for
// /api/visa/voa/eligibility-checks — mocked here (mirroring visa/match's
// page.test.tsx) so `fetchMock.toHaveBeenCalledTimes(1)` below still counts
// only the eligibility-checks call, and so tracker calls are assertable.
const trackerMocks = vi.hoisted(() => ({
  wizardStep: vi.fn(),
  wizardAbandoned: vi.fn(),
  formSubmitted: vi.fn(),
  formSubmitFailed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => ({
      viewed: vi.fn(),
      wizardStep: trackerMocks.wizardStep,
      wizardAbandoned: trackerMocks.wizardAbandoned,
      formSubmitted: trackerMocks.formSubmitted,
      formSubmitFailed: trackerMocks.formSubmitFailed,
    }),
  };
});

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function fillIssuanceUpToLastStep() {
  fireEvent.click(
    screen.getByRole("button", { name: /Get a new Visa on Arrival/ }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.click(screen.getByRole("button", { name: "Tourism" }));
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Nationality"), {
    target: { value: "ITA" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Entry date"), {
    target: { value: "2026-09-01" },
  });
  fireEvent.change(screen.getByLabelText("Passport expiry date"), {
    target: { value: "2027-09-01" },
  });
  fireEvent.click(
    screen.getByLabelText("Storage and deletion notice acknowledgement"),
  );
}

function fillIssuanceHappyPath() {
  fillIssuanceUpToLastStep();
  fireEvent.click(screen.getByRole("button", { name: "See result" }));
}

describe("VoaEligibilityPage — wire contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    fetchMock.mockReset();
  });

  it("posts an issuance request matching EligibilityCheckRequest, with no extension-only fields", async () => {
    fetchMock.mockResolvedValue({
      status: 201,
      headers: new Headers({ Location: "/visa/voa/opaque-id-123" }),
    });
    render(<VoaEligibilityPage />);
    fillIssuanceHappyPath();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/visa/voa/eligibility-checks");
    expect(init.headers["Idempotency-Key"]).toBeTruthy();
    expect(init.headers["Idempotency-Key"].length).toBeGreaterThanOrEqual(16);

    const body = JSON.parse(init.body);
    expect(body).toMatchObject({
      case_type: "issuance",
      nationality: "ITA",
      purpose: "tourism",
      entry_date: "2026-09-01",
      passport_expiry_date: "2027-09-01",
      travellers: 1,
      self_pay: true,
      extension_already_used: false,
      retention_notice_acknowledged: true,
    });
    // Contract allOf: voa_expiry_date is forbidden outside `extension`.
    expect(body).not.toHaveProperty("voa_expiry_date");

    // Telemetry: field NAMES only (Law 2) — the same payload_keys-only
    // pattern visa/match's W0b fix established, never any answer value.
    expect(trackerMocks.formSubmitted).toHaveBeenCalledWith(
      expect.arrayContaining([
        "case_type",
        "nationality",
        "purpose",
        "entry_date",
        "passport_expiry_date",
      ]),
    );
    const submittedWire = JSON.stringify(trackerMocks.formSubmitted.mock.calls);
    expect(submittedWire).not.toContain("ITA");
    expect(submittedWire).not.toContain("2026-09-01");
  });

  it("asks for the current VOA expiry date on the extension path and sends it", async () => {
    fetchMock.mockResolvedValue({
      status: 201,
      headers: new Headers({ Location: "/visa/voa/opaque-id-456" }),
    });
    render(<VoaEligibilityPage />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /Extend a Visa on Arrival I already have/,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Tourism" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Nationality"), {
      target: { value: "ITA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Entry date"), {
      target: { value: "2026-09-01" },
    });
    fireEvent.change(screen.getByLabelText("Passport expiry date"), {
      target: { value: "2027-09-01" },
    });
    fireEvent.change(
      screen.getByLabelText("Current Visa on Arrival expiry date"),
      { target: { value: "2026-09-10" } },
    );
    fireEvent.click(
      screen.getByLabelText("Storage and deletion notice acknowledgement"),
    );
    fireEvent.click(screen.getByRole("button", { name: "See result" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.case_type).toBe("extension");
    expect(body.voa_expiry_date).toBe("2026-09-10");
    expect(body.extension_already_used).toBe(false);
  });

  it("shows a WhatsApp fallback, never a raw error, when the API call fails", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    render(<VoaEligibilityPage />);
    fillIssuanceHappyPath();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(
      /couldn't check eligibility/i,
    );
    expect(
      screen.getByRole("link", { name: /message us on WhatsApp/i }),
    ).toBeInTheDocument();
    // Network failure (fetch rejects before any response) reports status null
    // — never a fabricated value — mirroring visa/match's W0b contract.
    expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
      "/api/visa/voa/eligibility-checks",
      null,
    );
  });
});

/**
 * Every attempt mints its own Idempotency-Key, so the key cannot dedupe a
 * double tap: two POSTs under two keys are two result rows. The guard has to
 * live in the page — a disabled button for the human, a ref for the tap that
 * lands before React has re-rendered it.
 */
describe("VoaEligibilityPage — double submit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    fetchMock.mockReset();
  });

  it("posts once and disables the button while the first submit is in flight", async () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    render(<VoaEligibilityPage />);
    fillIssuanceHappyPath();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const finish = screen.getByRole("button", { name: "See result" });
    await waitFor(() => expect(finish).toBeDisabled());
    expect(finish).toHaveAttribute("aria-busy", "true");

    fireEvent.click(finish);
    fireEvent.click(finish);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("collapses two taps landing in the same tick into one POST", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    render(<VoaEligibilityPage />);
    fillIssuanceUpToLastStep();

    const finish = screen.getByRole("button", { name: "See result" });
    act(() => {
      finish.click();
      finish.click();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("re-arms after a failure: the retry POSTs again under a fresh Idempotency-Key", async () => {
    fetchMock
      .mockRejectedValueOnce(new Error("network down"))
      .mockReturnValue(new Promise(() => {}));
    render(<VoaEligibilityPage />);
    fillIssuanceHappyPath();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    const finish = screen.getByRole("button", { name: "See result" });
    expect(finish).toBeEnabled();
    expect(finish).toHaveAttribute("aria-busy", "false");

    fireEvent.click(finish);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const keys = fetchMock.mock.calls.map(
      ([, init]) => init.headers["Idempotency-Key"] as string,
    );
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBeTruthy();
    expect(keys[0]).not.toBe(keys[1]);
  });
});

describe("VoaEligibilityPage — customer-facing surface", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    fetchMock.mockReset();
  });

  it("never leaks an internal service/class name (PricingTool etc.) into rendered copy", () => {
    render(<VoaEligibilityPage />);
    const rendered = document.body.textContent ?? "";
    // Guards the class of bug, not just the one string: any
    // TitleCase-word-immediately-followed-by-"Tool" token (PricingTool,
    // EligibilityTool, ...) is an internal identifier, never customer copy.
    expect(rendered).not.toMatch(/[A-Z][a-zA-Z]*Tool\b/);
  });

  it("has no Back control on step 1 (there is nowhere to go back to)", () => {
    render(<VoaEligibilityPage />);
    expect(
      screen.queryByRole("button", { name: "Back" }),
    ).not.toBeInTheDocument();
  });

  it("shows the Back control from step 2 onward", () => {
    render(<VoaEligibilityPage />);
    fireEvent.click(
      screen.getByRole("button", { name: /Get a new Visa on Arrival/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument();
  });

  it("tracks step progression (1-indexed) and abandonment mid-wizard", () => {
    render(<VoaEligibilityPage />);
    expect(trackerMocks.wizardStep).toHaveBeenCalledWith(1, 4);
    fireEvent.click(
      screen.getByRole("button", { name: /Get a new Visa on Arrival/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(trackerMocks.wizardStep).toHaveBeenCalledWith(2, 4);

    expect(trackerMocks.wizardAbandoned).not.toHaveBeenCalled();
    window.dispatchEvent(new Event("beforeunload"));
    expect(trackerMocks.wizardAbandoned).toHaveBeenCalledWith(1);
  });
});

/**
 * Hero handoff (garuda-voa/voa-r19-design lane).
 *
 * Measured on production 2026-09-16 at a 390px viewport: the page carried
 * two WhatsApp-matching anchors and NEITHER was tappable in the first
 * screen — the nav link rendered at height 0 inside the collapsed
 * hamburger, and "Get Started" sat in the footer. So a visitor who wanted a
 * human had to hunt. These pin the replacement, and pin it as a LEAD
 * control: the failure mode this lane must not reintroduce is a bare wa.me
 * anchor, which hands the visitor to WhatsApp while writing no
 * lead_intents row — the lead leaves the funnel and nobody knows.
 */
describe("VoaEligibilityPage — hero WhatsApp handoff", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    fetchMock.mockReset();
  });

  it("renders a WhatsApp control before the wizard, carrying the garuda_voa lead source", () => {
    render(<VoaEligibilityPage />);
    const cta = screen.getByRole("link", { name: /Talk to us on WhatsApp/i });
    expect(cta).toHaveAttribute("data-lead-source", "garuda_voa");
    // No-JS / capture-failure floor: the href alone still reaches the desk.
    expect(cta.getAttribute("href")).toMatch(/wa\.me|whatsapp/i);
  });

  it("captures a lead BEFORE handing off, and never posts an answer value", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        lead_intent_id: "li_test",
        whatsapp_url: "https://wa.me/628213454721?text=x",
      }),
    });
    render(<VoaEligibilityPage />);
    fireEvent.click(
      screen.getByRole("link", { name: /Talk to us on WhatsApp/i }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/lead/capture");
    const body = JSON.parse(init.body);
    expect(body.source).toBe("garuda_voa");
    expect(body.context).toMatchObject({ surface: "voa_hero" });
    // Law 2: the capture describes the SURFACE, never what the visitor typed.
    expect(JSON.stringify(body)).not.toMatch(/passport|nationality|ITA/i);
  });

  it("sits above the wizard, so the handoff is reachable without scrolling past step 1", () => {
    const { container } = render(<VoaEligibilityPage />);
    const cta = screen.getByRole("link", { name: /Talk to us on WhatsApp/i });
    const firstStepOption = screen.getByRole("button", {
      name: /Get a new Visa on Arrival/,
    });
    // Node.compareDocumentPosition: DOCUMENT_POSITION_FOLLOWING === 4.
    expect(
      cta.compareDocumentPosition(firstStepOption) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(container.querySelector(".voa-hero-wa")).not.toBeNull();
  });
});

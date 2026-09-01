import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const emitVisaOracleTelemetry = vi.hoisted(() => vi.fn());
const nonReversibleHash = vi.hoisted(() =>
  vi.fn(async (value: string) =>
    value.startsWith("{") ? "e".repeat(64) : "i".repeat(64),
  ),
);
vi.mock("../_lib/telemetry", async (importOriginal) => {
  const original = await importOriginal<typeof import("../_lib/telemetry")>();
  return { ...original, emitVisaOracleTelemetry, nonReversibleHash };
});

import {
  createInterviewSnapshot,
  flowReducer,
  initialFlowState,
  type FlowState,
} from "../_lib/flow";
import { VISA_ORACLE_IDENTITY_KEY } from "../_lib/evaluation-identity-store";
import {
  VISA_ORACLE_RESUME_KEY,
  saveInterviewResume,
} from "../_lib/resume-store";
import { makeVisaOracleResponse } from "../_lib/visa-oracle-test-fixture";
import { translate } from "../_lib/i18n";
import { OracleShell } from "./OracleShell";

const ANSWERS = [
  ["in_indonesia", "no"],
  // Offshore now asks a single permit-status gate question, converging
  // immediately on "no" (fixed 2026-08-24, D12 offshore-reachability P0,
  // then re-fixed same day after a funnel-cost review) — answered "no"
  // to preserve this fixture's original downstream intent.
  ["holds_stay_permit", "no"],
  ["overstay_days", "0"],
  ["nationalities", "US"],
  ["birth_date", "1990-01-01"],
  ["category", "tourism"],
  ["trip_scope", "single"],
  ["stay_days", "30"],
  ["entry_pattern", "SINGLE"],
  ["review_gate", "none"],
] as const;
type FixtureState = NonNullable<Parameters<typeof makeVisaOracleResponse>[0]>;

function verdictSnapshot(): ReturnType<typeof createInterviewSnapshot> {
  let state: FlowState = flowReducer(initialFlowState(), { type: "ADVANCE" });
  for (const [questionId, value] of ANSWERS) {
    state = flowReducer(state, { type: "ANSWER", questionId, value });
  }
  state = flowReducer(state, { type: "ADVANCE" });
  expect(state.history[state.history.length - 1]).toEqual({ kind: "verdict" });
  return createInterviewSnapshot(state, new Date());
}

function installVerdictResume(): void {
  expect(saveInterviewResume(verdictSnapshot(), { now: new Date() })).toBe(
    true,
  );
}

function engineFetch(
  state: FixtureState = "SUPPORTED_CANDIDATES",
  mode: "ENGINE" | "CURATED" = "ENGINE",
) {
  const response = makeVisaOracleResponse(state);
  response.mode = mode;
  return vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
}

function engineErrorResponse(status: number): Response {
  return new Response(JSON.stringify({ error: `HTTP ${status}` }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function expectStateHeading(state: FixtureState) {
  expect(
    await screen.findByRole("heading", {
      name: translate("en", `verdict.headline.${state}`),
    }),
  ).toBeInTheDocument();
}

async function completeFreshInterview(): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: /^start$/i }));
  fireEvent.click(
    await screen.findByRole("button", { name: /planning ahead/i }),
  );

  // Offshore now asks a single permit-status gate question before
  // converging (fixed 2026-08-24, D12 offshore-reachability P0, then
  // re-fixed same day after a funnel-cost review — see flow.ts's
  // `in_indonesia`/`holds_stay_permit` cases). "no" here converges
  // straight to overstay_days with no further permit questions — the
  // fact resolves from this answer alone via fact-mapper.ts's
  // synthesized NO_STAY_PERMIT (see fact-mapper.test.ts for that proof).
  await screen.findByRole("heading", {
    name: /do you currently hold a limited or permanent stay permit/i,
  });
  fireEvent.click(await screen.findByRole("button", { name: /^no$/i }));

  fireEvent.change(await screen.findByRole("spinbutton"), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

  fireEvent.change(await screen.findByRole("combobox"), {
    target: { value: "US" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^add country$/i }));
  fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

  const birthDate =
    document.querySelector<HTMLInputElement>('input[type="date"]');
  expect(birthDate).not.toBeNull();
  fireEvent.change(birthDate!, { target: { value: "1990-01-01" } });
  fireEvent.click(screen.getByRole("button", { name: /see my options/i }));

  fireEvent.click(
    await screen.findByRole("button", { name: /tourism.*short visit/i }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: /one main purpose/i }),
  );
  fireEvent.change(await screen.findByRole("spinbutton"), {
    target: { value: "30" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
  fireEvent.click(await screen.findByRole("button", { name: /^one entry$/i }));
  fireEvent.click(
    await screen.findByRole("checkbox", { name: /none of these apply/i }),
  );
  fireEvent.click(screen.getByRole("button", { name: /see my options/i }));

  await screen.findByRole("heading", { name: /here.s what you told us/i });
  fireEvent.click(
    screen.getByRole("button", {
      name: translate("en", "confirmation.cta"),
    }),
  );
}

describe("OracleShell authoritative evaluate integration", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    emitVisaOracleTelemetry.mockReset();
    nonReversibleHash.mockClear();
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "ENGINE");
    installVerdictResume();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it.each([
    "SUPPORTED_CANDIDATES",
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
    "TEMPORARILY_UNAVAILABLE",
  ] as const)("renders the real ENGINE state %s", async (state) => {
    global.fetch = engineFetch(state);
    render(<OracleShell />);

    await expectStateHeading(state);
    expect(global.fetch).toHaveBeenCalledOnce();
    if (state === "SUPPORTED_CANDIDATES") {
      expect(screen.getByText("Visit Visa C1")).toBeInTheDocument();
    } else {
      expect(screen.queryByText("Visit Visa C1")).toBeNull();
    }
    if (state !== "TEMPORARILY_UNAVAILABLE") {
      await waitFor(() =>
        expect(
          window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY),
        ).toBeNull(),
      );
    }
  });

  it("never renders candidates from CURATED/SHADOW and still submits once", async () => {
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "SHADOW");
    global.fetch = engineFetch("SUPPORTED_CANDIDATES", "CURATED");
    render(<OracleShell />);

    expect(
      await screen.findByRole("heading", {
        name: translate("en", "verdict.provenance_headline.SHADOW"),
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Visit Visa C1")).toBeNull();
    expect(global.fetch).toHaveBeenCalledOnce();
  });

  it("fails closed for a CURATED response in ENGINE mode, and says so honestly", async () => {
    global.fetch = engineFetch("SUPPORTED_CANDIDATES", "CURATED");
    render(<OracleShell />);

    // The load-bearing assertion, unchanged: a CURATED decision never
    // becomes visible authority. This is what "fails closed" means and it
    // is what the internal-preview test below cites as its innocence case.
    expect(screen.queryByText("Visit Visa C1")).toBeNull();

    // What DID change: this visitor used to be told "No evaluation was
    // submitted", which is false -- the server evaluated, sealed and
    // persisted a real decision, and only declined to render it as
    // authority because public enforcement is off. That is the identical
    // situation the SHADOW-mode test directly above covers, so it now
    // shows the identical, true headline.
    expect(
      await screen.findByRole("heading", {
        name: translate("en", "verdict.provenance_headline.SHADOW"),
      }),
    ).toBeInTheDocument();

    // Guard against regressing to the accusatory copy. Asserted on the
    // literal sentence rather than on the provenance label, so a future
    // refactor that reroutes this back into the client-guard bucket fails
    // here even if it renames the label.
    expect(screen.queryByText(/No evaluation was submitted/i)).toBeNull();
    expect(
      screen.queryByRole("heading", {
        name: translate("en", "verdict.provenance_headline.CLIENT_GUARD"),
      }),
    ).toBeNull();
  });

  // The PIN-gated internal preview. Its innocence case is the test directly
  // above: without `internalMode`, the very same CURATED response must still
  // fail closed and show no candidates.
  it("internal preview renders the real decision from a CURATED response", async () => {
    global.fetch = engineFetch("SUPPORTED_CANDIDATES", "CURATED");
    render(<OracleShell internalMode />);

    expect(await screen.findByText("Visit Visa C1")).toBeInTheDocument();
    // Never show an engine decision without saying what it is.
    expect(screen.getByText(/INTERNAL PREVIEW/)).toBeInTheDocument();
  });

  it("internal preview is decided before the frontend SHADOW branch", async () => {
    // Ordering is deliberate: a SHADOW-configured frontend would otherwise
    // swallow the decision the tester unlocked specifically to see.
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "SHADOW");
    global.fetch = engineFetch("SUPPORTED_CANDIDATES", "CURATED");
    render(<OracleShell internalMode />);

    expect(await screen.findByText("Visit Visa C1")).toBeInTheDocument();
  });

  it("public traffic never sees the internal preview notice", async () => {
    global.fetch = engineFetch("SUPPORTED_CANDIDATES");
    render(<OracleShell />);

    await expectStateHeading("SUPPORTED_CANDIDATES");
    expect(screen.queryByText(/INTERNAL PREVIEW/)).toBeNull();
  });

  it("never claims no evaluation was submitted when the engine adapter rejects one review-hold citation", async () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.sources[0].canonical_url = "https://imigrasi.go.id.evil.test/x";
    response.decision.review_reasons[0].source_refs = [
      response.sources[0].source_record_id,
    ];
    global.fetch = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    render(<OracleShell />);

    await expectStateHeading("HUMAN_REVIEW_REQUIRED");
    expect(
      screen.getByText(translate("en", "outcome.human_review_body")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no evaluation was submitted/i)).toBeNull();
    expect(screen.queryByText("Client safety hold")).toBeNull();
  });

  it("never claims no evaluation was submitted when strict parsing rejects an unrelated field", async () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    const raw = JSON.parse(JSON.stringify(response)) as Record<string, unknown>;
    (raw.sources as Array<Record<string, unknown>>)[0].is_primary_authority =
      null;
    global.fetch = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify(raw), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    render(<OracleShell />);

    await expectStateHeading("HUMAN_REVIEW_REQUIRED");
    expect(screen.queryByText(/no evaluation was submitted/i)).toBeNull();
    expect(screen.queryByText("Client safety hold")).toBeNull();
  });

  it("keeps automatic network retry byte-identical and renders no fabricated result", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      throw new TypeError("network down");
    });
    global.fetch = fetchMock;
    render(<OracleShell />);

    expect(
      await screen.findByRole("heading", {
        name: translate("en", "verdict.provenance_headline.NETWORK_FAILURE"),
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Visit Visa C1")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const first = fetchMock.mock.calls[0][1];
    const second = fetchMock.mock.calls[1][1];
    expect(second?.body).toBe(first?.body);
    expect(new Headers(second?.headers).get("Idempotency-Key")).toBe(
      new Headers(first?.headers).get("Idempotency-Key"),
    );
  });

  it("keeps an exhausted HTTP 429 operationally retryable", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => engineErrorResponse(429));
    global.fetch = fetchMock;
    render(<OracleShell />);

    expect(
      await screen.findByRole("heading", {
        name: translate("en", "verdict.provenance_headline.NETWORK_FAILURE"),
      }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(
      screen.getByRole("button", { name: "Retry verified evaluation" }),
    ).toBeVisible();
  });

  it.each([409, 422])(
    "keeps HTTP %s non-retryable after the client guard",
    async (status) => {
      const fetchMock = vi.fn<typeof fetch>(async () =>
        engineErrorResponse(status),
      );
      global.fetch = fetchMock;
      render(<OracleShell />);

      expect(
        await screen.findByRole("heading", {
          name: translate("en", "verdict.provenance_headline.CLIENT_GUARD"),
        }),
      ).toBeInTheDocument();
      expect(fetchMock).toHaveBeenCalledOnce();
      expect(
        screen.queryByRole("button", { name: "Retry verified evaluation" }),
      ).toBeNull();
    },
  );

  it("keeps resume-off retry identity in memory and never writes its fact hash to sessionStorage", async () => {
    window.sessionStorage.clear();
    const identityValuesSeenByFetch: Array<string | null> = [];
    let attempt = 0;
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    const fetchMock = vi.fn<typeof fetch>(async () => {
      attempt += 1;
      identityValuesSeenByFetch.push(
        window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY),
      );
      if (attempt === 1) throw new TypeError("network down");
      return new Response(JSON.stringify(response), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    global.fetch = fetchMock;
    render(
      <StrictMode>
        <OracleShell />
      </StrictMode>,
    );

    await completeFreshInterview();
    await expectStateHeading("SUPPORTED_CANDIDATES");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const first = fetchMock.mock.calls[0][1];
    const second = fetchMock.mock.calls[1][1];
    expect(second?.body).toBe(first?.body);
    expect(new Headers(second?.headers).get("Idempotency-Key")).toBe(
      new Headers(first?.headers).get("Idempotency-Key"),
    );
    expect(identityValuesSeenByFetch).toEqual([null, null]);
    expect(window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY)).toBeNull();
  });

  it("replays a byte-identical resume-on evaluation after a remount", async () => {
    const fetchMock = engineFetch("TEMPORARILY_UNAVAILABLE");
    global.fetch = fetchMock;
    const firstMount = render(<OracleShell />);
    await expectStateHeading("TEMPORARILY_UNAVAILABLE");
    expect(
      window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY),
    ).not.toBeNull();

    firstMount.unmount();
    render(<OracleShell />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await expectStateHeading("TEMPORARILY_UNAVAILABLE");

    const first = fetchMock.mock.calls[0][1];
    const reload = fetchMock.mock.calls[1][1];
    expect(reload?.body).toBe(first?.body);
    expect(new Headers(reload?.headers).get("Idempotency-Key")).toBe(
      new Headers(first?.headers).get("Idempotency-Key"),
    );
  });

  it("rotates assessment and idempotency identity on explicit TEMP retry", async () => {
    const fetchMock = engineFetch("TEMPORARILY_UNAVAILABLE");
    global.fetch = fetchMock;
    render(<OracleShell />);
    await expectStateHeading("TEMPORARILY_UNAVAILABLE");

    fireEvent.click(
      screen.getByRole("button", { name: "Retry verified evaluation" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const first = fetchMock.mock.calls[0][1];
    const second = fetchMock.mock.calls[1][1];
    expect(new Headers(second?.headers).get("Idempotency-Key")).not.toBe(
      new Headers(first?.headers).get("Idempotency-Key"),
    );
    expect(
      (JSON.parse(String(second?.body)) as { assessment_id: string })
        .assessment_id,
    ).not.toBe(
      (JSON.parse(String(first?.body)) as { assessment_id: string })
        .assessment_id,
    );
  });

  it("clears a retryable resume when the interview is restarted", async () => {
    global.fetch = engineFetch("TEMPORARILY_UNAVAILABLE");
    render(<OracleShell />);
    await expectStateHeading("TEMPORARILY_UNAVAILABLE");
    expect(
      window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY),
    ).not.toBeNull();
    expect(
      window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY),
    ).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /start over/i }));
    expect(window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY)).toBeNull();
    expect(
      await screen.findByRole("button", { name: /^start$/i }),
    ).toBeInTheDocument();
  });

  it("survives StrictMode effect replacement with one final authority and no spinner", async () => {
    const fetchMock = engineFetch();
    global.fetch = fetchMock;
    render(
      <StrictMode>
        <OracleShell />
      </StrictMode>,
    );

    await expectStateHeading("SUPPORTED_CANDIDATES");
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(
      screen.queryByText("Checking the verified Visa Oracle engine…"),
    ).toBeNull();
  });

  it("starts a fresh evaluation after leaving and revisiting the same verdict", async () => {
    const fetchMock = engineFetch();
    global.fetch = fetchMock;
    render(<OracleShell />);
    await expectStateHeading("SUPPORTED_CANDIDATES");

    fireEvent.click(screen.getByRole("button", { name: "Edit answers" }));
    fireEvent.click(
      await screen.findByRole("button", {
        name: translate("en", "confirmation.cta"),
      }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await expectStateHeading("SUPPORTED_CANDIDATES");
    const first = fetchMock.mock.calls[0][1];
    const second = fetchMock.mock.calls[1][1];
    expect(new Headers(second?.headers).get("Idempotency-Key")).not.toBe(
      new Headers(first?.headers).get("Idempotency-Key"),
    );
    expect(
      (JSON.parse(String(second?.body)) as { assessment_id: string })
        .assessment_id,
    ).not.toBe(
      (JSON.parse(String(first?.body)) as { assessment_id: string })
        .assessment_id,
    );
  });

  it("uses only a hash of the random assessment UUID for telemetry", async () => {
    global.fetch = engineFetch();
    render(<OracleShell />);
    await expectStateHeading("SUPPORTED_CANDIDATES");

    const engineEvent = emitVisaOracleTelemetry.mock.calls.find(
      ([event]) => event.event === "visa_oracle_v2_engine_result",
    )?.[0];
    expect(engineEvent?.correlationHash).toBe("i".repeat(64));
    expect(engineEvent?.correlationHash).not.toBe("e".repeat(64));
    expect(nonReversibleHash).toHaveBeenCalledWith(
      expect.stringMatching(/^[0-9a-f-]{36}$/),
    );
  });
});

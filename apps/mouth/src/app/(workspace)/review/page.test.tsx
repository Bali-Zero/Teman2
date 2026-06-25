import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReviewPage from "./page";

const createClientMock = vi.hoisted(() => vi.fn());
const getProfileMock = vi.hoisted(() => vi.fn());

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getToken: vi.fn(() => null),
  getProfile: getProfileMock,
  crm: { createClient: createClientMock },
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

const NO_MATCH_PROPOSAL = {
  proposal_id: 2,
  doc_type: "passport",
  decision: "NO_MATCH",
  source: "drive",
  status: "review_pending",
  received_by: null,
  entity_candidates: [],
  extracted_fields: {
    name: "Walter White",
    nationality: "US",
    passport_no: "P1234567",
    dob: "1965-09-07",
    expiry: "2030-01-01",
  },
  created_at: "2026-06-15T10:00:00Z",
};

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint.startsWith("/api/intake/review/queue")) {
        return {
          items: [
            {
              proposal_id: 1,
              doc_type: "passport",
              decision: "AUTO_ATTACH",
              source: "whatsapp",
              status: "review_pending",
              received_by: "adit@balizero.com",
              entity_candidates: [
                {
                  client_id: 21,
                  full_name: "Client One",
                },
              ],
              extracted_fields: {},
              created_at: "2026-06-15T09:00:00Z",
            },
            NO_MATCH_PROPOSAL,
          ],
        };
      }
      if (endpoint === "/api/intake/review/document-categories") {
        return { items: [] };
      }
      if (endpoint === `/api/intake/review/${NO_MATCH_PROPOSAL.proposal_id}`) {
        return NO_MATCH_PROPOSAL;
      }
      if (/\/clients\/\d+\/practices$/.test(endpoint)) {
        return { items: [] };
      }
      throw new Error(`Unexpected GET ${endpoint}`);
    });
    apiMock.post.mockImplementation(async (endpoint: string) => {
      if (endpoint.endsWith("/claim")) {
        return {
          proposal_id: NO_MATCH_PROPOSAL.proposal_id,
          claim_token: "tok-1",
          lease_expires_at: "2026-06-15T10:15:00Z",
        };
      }
      if (endpoint.endsWith("/approve")) {
        return {
          proposal_id: NO_MATCH_PROPOSAL.proposal_id,
          dry_run: false,
          outcome: "committed",
          status: "routed",
        };
      }
      return {};
    });
  });

  it("shows the receiving operator on each review card", async () => {
    render(<ReviewPage />);

    expect(
      await screen.findByText("Operator: adit@balizero.com"),
    ).toBeVisible();
    expect(screen.getByText("Operator: unassigned")).toBeVisible();
  });

  it("leads a NO_MATCH proposal with a 'Create new client' CTA prefilled from the extracted fields", async () => {
    render(<ReviewPage />);

    // Open the NO_MATCH proposal (the second card has no proposed client).
    const reviewButtons = await screen.findAllByRole("button", {
      name: "Review",
    });
    // The NO_MATCH card is the one labelled "No client matched — needs a decision".
    expect(
      screen.getByText("No client matched — needs a decision"),
    ).toBeVisible();
    fireEvent.click(reviewButtons[1]);

    // The primary, helpful CTA — NOT an error.
    expect(await screen.findByText("➕ New client")).toBeVisible();
    expect(
      screen.getByText(
        "No existing client matched — is this a new client? Create one from the document data:",
      ),
    ).toBeVisible();

    // Prefilled from extracted_fields (intake schema → CRM field mapping).
    // Some values also appear in the raw "Extracted fields" editor above, so
    // assert presence (>=1), not uniqueness.
    expect(screen.getAllByDisplayValue("Walter White").length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByDisplayValue("US").length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue("P1234567").length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue("1965-09-07").length).toBeGreaterThan(0);
    expect(screen.getAllByDisplayValue("2030-01-01").length).toBeGreaterThan(0);
  });

  it("creates the new client then files the document via the existing approve flow", async () => {
    getProfileMock.mockResolvedValue({ email: "adit@balizero.com" });
    createClientMock.mockResolvedValue({
      id: 999,
      full_name: "Walter White",
      email: undefined,
      phone: undefined,
      nationality: "US",
      assigned_to: "adit@balizero.com",
    });

    render(<ReviewPage />);

    const reviewButtons = await screen.findAllByRole("button", {
      name: "Review",
    });
    fireEvent.click(reviewButtons[1]);

    const createBtn = await screen.findByRole("button", {
      name: "➕ Create new client + file this document",
    });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(createClientMock).toHaveBeenCalledTimes(1);
    });
    // Created with the prefilled name + the current user's email as creator.
    const [payload, createdBy] = createClientMock.mock.calls[0];
    expect(payload.full_name).toBe("Walter White");
    expect(payload.passport_number).toBe("P1234567");
    expect(createdBy).toBe("adit@balizero.com");

    // The SAME approve path files the doc to the new client_id (999).
    await waitFor(() => {
      const approveCall = apiMock.post.mock.calls.find((c: unknown[]) =>
        String(c[0]).endsWith("/approve"),
      );
      expect(approveCall).toBeTruthy();
      expect((approveCall![1] as { client_id?: number }).client_id).toBe(999);
    });
  });

  // ── View-first / read-only-on-409 (the PROD "Could not open the document"
  //    bug: claiming a terminal `routed` proposal 409'd before any view) ──────
  // Placeholder ids only — never real client PII (UU PDP, intake is PII-L2).
  const ROUTED_DETAIL = {
    proposal_id: 1,
    doc_type: "passport",
    decision: "AUTO_ATTACH",
    source: "whatsapp",
    status: "routed",
    received_by: "adit@balizero.com",
    entity_candidates: [{ client_id: 21, full_name: "Client One" }],
    extracted_fields: {},
    created_at: "2026-06-15T09:00:00Z",
    routing: {},
  };
  const PENDING_DETAIL = { ...ROUTED_DETAIL, status: "review_pending" };

  it("opens a terminal (routed) proposal READ-ONLY without an error and without claiming", async () => {
    // The detail GET for proposal 1 reports a terminal status (it turned
    // `routed` between the pending-queue load and the click — the PROD repro).
    const baseGet = apiMock.get.getMockImplementation()!;
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/intake/review/1") return ROUTED_DETAIL;
      if (/^\/api\/intake\/review\/clients\//.test(endpoint))
        return { items: [] };
      return baseGet(endpoint);
    });

    render(<ReviewPage />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Review" }))[0]);

    // Read-only notice is shown…
    expect(await screen.findByText(/already filed — view only/i)).toBeVisible();
    // …the generic failure toast is NOT shown…
    expect(
      screen.queryByText("Could not open the document."),
    ).not.toBeInTheDocument();
    // …and we NEVER attempted to claim a terminal proposal.
    expect(apiMock.post).not.toHaveBeenCalled();

    // Actions are disabled in read-only mode.
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();

    // …and the now-terminal row is PRUNED from the in-memory queue so it can no
    // longer be reopened as a zombie (it turned terminal mid-session — a full
    // loadQueue() would also drop it, this does it eagerly). The list started
    // with two cards (proposal 1 + the NO_MATCH proposal); after opening the
    // terminal one, only the NO_MATCH 'Review' button remains.
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Review" })).toHaveLength(1),
    );
  });

  it("falls back to read-only 'claimed by another reviewer' on a live-claim 409", async () => {
    const baseGet = apiMock.get.getMockImplementation()!;
    apiMock.get.mockImplementation(async (endpoint: string) => {
      // Detail still says claimable…
      if (endpoint === "/api/intake/review/1") return PENDING_DETAIL;
      if (/^\/api\/intake\/review\/clients\//.test(endpoint))
        return { items: [] };
      return baseGet(endpoint);
    });
    // …but the claim races and 409s, surfacing the FastAPI detail verbatim.
    apiMock.post.mockReset();
    apiMock.post.mockRejectedValueOnce(
      new Error(
        "Proposal not claimable (status=review_claimed, lease_owner=other@balizero.com)",
      ),
    );

    render(<ReviewPage />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Review" }))[0]);

    expect(
      await screen.findByText(/claimed by another reviewer — view only/i),
    ).toBeVisible();
    expect(
      screen.queryByText("Could not open the document."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  });

  it("claims and enables actions when the proposal is genuinely claimable", async () => {
    const baseGet = apiMock.get.getMockImplementation()!;
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/intake/review/1") return PENDING_DETAIL;
      if (/^\/api\/intake\/review\/clients\//.test(endpoint))
        return { items: [] };
      return baseGet(endpoint);
    });
    // beforeEach's apiMock.post already returns a claim_token on /claim.

    render(<ReviewPage />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Review" }))[0]);

    // The claim was attempted exactly once on the claim endpoint.
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledTimes(1));
    expect(apiMock.post).toHaveBeenCalledWith("/api/intake/review/1/claim", {});
    // No read-only notice, and a candidate is pre-selected → Approve enabled.
    expect(screen.queryByText(/view only/i)).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled(),
    );
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("shows the generic failure only when the detail GET itself fails", async () => {
    const baseGet = apiMock.get.getMockImplementation()!;
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/intake/review/1") throw new Error("HTTP 500");
      return baseGet(endpoint);
    });

    render(<ReviewPage />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Review" }))[0]);

    expect(
      await screen.findByText("Could not open the document."),
    ).toBeVisible();
    // The detail GET failed before any claim attempt.
    expect(apiMock.post).not.toHaveBeenCalled();
  });
});

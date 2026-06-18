import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReviewPage from "./page";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getToken: vi.fn(() => null),
  getProfile: vi.fn(async () => ({ email: "adit@balizero.com" })),
  crm: { createClient: vi.fn() },
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

// jsdom has no fetch; the blob-preview effect calls fetch(). A rejected stub
// keeps the preview path quiet without touching the open/claim logic under test.
const fetchMock = vi.hoisted(() =>
  vi.fn(async () => {
    throw new Error("no preview in test");
  }),
);

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

const PENDING_DETAIL = {
  ...ROUTED_DETAIL,
  status: "review_pending",
};

function mockQueueOnly() {
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
            entity_candidates: [{ client_id: 21, full_name: "Client One" }],
            extracted_fields: {},
            created_at: "2026-06-15T09:00:00Z",
          },
        ],
      };
    }
    if (endpoint === "/api/intake/review/document-categories") {
      return { items: [] };
    }
    throw new Error(`Unexpected GET ${endpoint}`);
  });
}

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
    mockQueueOnly();
  });

  it("shows the receiving operator on each review card", async () => {
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
              entity_candidates: [{ client_id: 21, full_name: "Client One" }],
              extracted_fields: {},
              created_at: "2026-06-15T09:00:00Z",
            },
            {
              proposal_id: 2,
              doc_type: "npwp",
              decision: "AMBIGUOUS",
              source: "drive",
              status: "review_pending",
              received_by: null,
              entity_candidates: [],
              extracted_fields: {},
              created_at: "2026-06-15T10:00:00Z",
            },
          ],
        };
      }
      if (endpoint === "/api/intake/review/document-categories") {
        return { items: [] };
      }
      throw new Error(`Unexpected GET ${endpoint}`);
    });

    render(<ReviewPage />);

    expect(
      await screen.findByText("Operator: adit@balizero.com"),
    ).toBeVisible();
    expect(screen.getByText("Operator: unassigned")).toBeVisible();
  });

  it("opens a terminal (routed) proposal READ-ONLY without an error and without claiming", async () => {
    // The detail GET reports a terminal status (it turned `routed` between the
    // pending-queue load and the click — the exact PROD repro).
    const baseGet = apiMock.get.getMockImplementation()!;
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/intake/review/1") return ROUTED_DETAIL;
      if (/^\/api\/intake\/review\/clients\//.test(endpoint))
        return { items: [] };
      return baseGet(endpoint);
    });

    const user = userEvent.setup();
    render(<ReviewPage />);

    await user.click(await screen.findByRole("button", { name: "Review" }));

    // Read-only notice is shown…
    expect(
      await screen.findByText(/already filed — view only/i),
    ).toBeVisible();
    // …the generic failure toast is NOT shown…
    expect(
      screen.queryByText("Could not open the document."),
    ).not.toBeInTheDocument();
    // …and we NEVER attempted to claim a terminal proposal.
    expect(apiMock.post).not.toHaveBeenCalled();

    // Actions are disabled in read-only mode.
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
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
    apiMock.post.mockRejectedValueOnce(
      new Error(
        "Proposal not claimable (status=review_claimed, lease_owner=other@balizero.com)",
      ),
    );

    const user = userEvent.setup();
    render(<ReviewPage />);

    await user.click(await screen.findByRole("button", { name: "Review" }));

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
    apiMock.post.mockResolvedValueOnce({
      proposal_id: 1,
      claim_token: "tok-123",
      lease_expires_at: "2026-06-15T09:15:00Z",
    });

    const user = userEvent.setup();
    render(<ReviewPage />);

    await user.click(await screen.findByRole("button", { name: "Review" }));

    // The claim was attempted exactly once on the claim endpoint.
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledTimes(1));
    expect(apiMock.post).toHaveBeenCalledWith(
      "/api/intake/review/1/claim",
      {},
    );
    // No read-only notice, and a candidate is pre-selected → Approve enabled.
    expect(
      screen.queryByText(/view only/i),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled(),
    );
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("shows the generic failure only when the detail GET itself fails", async () => {
    const baseGet = apiMock.get.getMockImplementation()!;
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/intake/review/1")
        throw new Error("HTTP 500");
      return baseGet(endpoint);
    });

    const user = userEvent.setup();
    render(<ReviewPage />);

    await user.click(await screen.findByRole("button", { name: "Review" }));

    expect(
      await screen.findByText("Could not open the document."),
    ).toBeVisible();
    // The detail GET failed before any claim attempt.
    expect(apiMock.post).not.toHaveBeenCalled();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Fix #2 — "create new client" from the review panel (NO_MATCH / LINK_CANDIDATE)
// ─────────────────────────────────────────────────────────────────────────────

// Placeholder ids only — never real client PII (UU PDP, intake is PII-L2).
const NO_MATCH_DETAIL = {
  proposal_id: 1,
  doc_type: "passport",
  decision: "NO_MATCH",
  source: "whatsapp",
  status: "review_pending",
  received_by: "adit@balizero.com",
  entity_candidates: [],
  extracted_fields: {},
  created_at: "2026-06-15T09:00:00Z",
  routing: {},
};

const AUTO_ATTACH_DETAIL = {
  ...NO_MATCH_DETAIL,
  decision: "AUTO_ATTACH",
  entity_candidates: [{ client_id: 21, full_name: "Existing One" }],
};

/** Queue with one card so the modal can be opened, plus a detail responder. */
function mockQueueAndDetail(detail: Record<string, unknown>) {
  apiMock.get.mockImplementation(async (endpoint: string) => {
    if (endpoint.startsWith("/api/intake/review/queue")) {
      return {
        items: [
          {
            proposal_id: 1,
            doc_type: "passport",
            decision: detail.decision,
            source: "whatsapp",
            status: "review_pending",
            received_by: "adit@balizero.com",
            entity_candidates: detail.entity_candidates,
            extracted_fields: {},
            created_at: "2026-06-15T09:00:00Z",
          },
        ],
      };
    }
    if (endpoint === "/api/intake/review/document-categories")
      return { items: [] };
    if (endpoint === "/api/intake/review/1") return detail;
    if (/^\/api\/intake\/review\/clients\//.test(endpoint))
      return { items: [] };
    throw new Error(`Unexpected GET ${endpoint}`);
  });
}

describe("ReviewPage — create new client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
    apiMock.getProfile.mockResolvedValue({ email: "adit@balizero.com" });
  });

  it("offers 'Crea nuovo cliente' for a NO_MATCH claimable proposal", async () => {
    mockQueueAndDetail(NO_MATCH_DETAIL);
    apiMock.post.mockResolvedValueOnce({
      proposal_id: 1,
      claim_token: "tok-1",
      lease_expires_at: "2026-06-15T09:15:00Z",
    });

    const user = userEvent.setup();
    render(<ReviewPage />);
    await user.click(await screen.findByRole("button", { name: "Review" }));

    expect(
      await screen.findByRole("button", { name: "+ Crea nuovo cliente" }),
    ).toBeEnabled();
  });

  it("does NOT offer create-client for an AUTO_ATTACH proposal", async () => {
    mockQueueAndDetail(AUTO_ATTACH_DETAIL);
    apiMock.post.mockResolvedValueOnce({
      proposal_id: 1,
      claim_token: "tok-1",
      lease_expires_at: "2026-06-15T09:15:00Z",
    });

    const user = userEvent.setup();
    render(<ReviewPage />);
    await user.click(await screen.findByRole("button", { name: "Review" }));

    // The detail modal is open (Destination heading present)…
    expect(await screen.findByText("Destination")).toBeVisible();
    // …but the create-client entry point is NOT rendered.
    expect(
      screen.queryByRole("button", { name: "+ Crea nuovo cliente" }),
    ).not.toBeInTheDocument();
  });

  it("keeps create-client DISABLED in read-only mode (NO_MATCH but terminal)", async () => {
    mockQueueAndDetail({ ...NO_MATCH_DETAIL, status: "routed" });
    // status is terminal → openDetail never claims; if the UI mistakenly tried,
    // a 409 stub guards against a false positive.
    apiMock.post.mockRejectedValue(
      new Error("Proposal not claimable (status=routed, lease_owner=None)"),
    );

    const user = userEvent.setup();
    render(<ReviewPage />);
    await user.click(await screen.findByRole("button", { name: "Review" }));

    // Read-only notice shown, no claim held → no create-client entry point.
    expect(
      await screen.findByText(/already filed — view only/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "+ Crea nuovo cliente" }),
    ).not.toBeInTheDocument();
    // We never claimed a terminal proposal.
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it("creates a client and sets it as the destination (enables Approve)", async () => {
    mockQueueAndDetail(NO_MATCH_DETAIL);
    // 1st post = claim (review opens editable).
    apiMock.post.mockResolvedValueOnce({
      proposal_id: 1,
      claim_token: "tok-1",
      lease_expires_at: "2026-06-15T09:15:00Z",
    });
    // createClient returns the new client (placeholder id).
    apiMock.crm.createClient.mockResolvedValueOnce({
      id: 99,
      full_name: "Brand New",
      assigned_to: "adit@balizero.com",
    });

    const user = userEvent.setup();
    render(<ReviewPage />);
    await user.click(await screen.findByRole("button", { name: "Review" }));

    await user.click(
      await screen.findByRole("button", { name: "+ Crea nuovo cliente" }),
    );
    await user.type(
      await screen.findByLabelText("New client full name"),
      "Brand New",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Create client & set as destination",
      }),
    );

    // createClient called with the typed name + the operator email as created_by.
    await waitFor(() =>
      expect(apiMock.crm.createClient).toHaveBeenCalledTimes(1),
    );
    const [payload, createdBy] = apiMock.crm.createClient.mock.calls[0];
    expect(payload.full_name).toBe("Brand New");
    expect(createdBy).toBe("adit@balizero.com");

    // Success notice + the new client is now the destination → Approve enabled.
    expect(
      await screen.findByText(/New client created: Brand New/i),
    ).toBeVisible();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled(),
    );
  });
});

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReviewPage from "./page";

const createClientMock = vi.hoisted(() => vi.fn());
const getProfileMock = vi.hoisted(() => vi.fn());
const getUserProfileMock = vi.hoisted(() => vi.fn());

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getToken: vi.fn(() => null),
  getProfile: getProfileMock,
  getUserProfile: getUserProfileMock,
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
    // Default signed-in viewer for every test below: an admin, so the
    // NULL-received_by NO_MATCH fixture (admin-only by the backend
    // contract) still paints copper unless a test overrides the identity.
    getUserProfileMock.mockReturnValue({
      email: "adit@balizero.com",
      role: "admin",
    });
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

  it("shows the receiving operator on each review row, at both widths", async () => {
    // RE-PINNED with the 390px column collapse (SAETTA-R19K K2b), not
    // weakened. Below 768px the Operator and Received columns leave the grid
    // and their values are re-rendered on the row's secondary line, so each
    // operator string is emitted TWICE — once in the desktop grid cell and
    // once on the phone line, with a media query hiding whichever does not
    // apply. jsdom evaluates no media query, so both are in the DOM here.
    //
    // The two copies are pinned SEPARATELY, by the text each one carries.
    // The desktop grid cell is the BARE address: its column header already
    // says OPERATOR, and repeating the word there cost ~70px and truncated
    // every address to "member@example.t..." at 1440. The phone line KEEPS
    // the "Operator:" prefix, because there the values run together with no
    // header to name them.
    //
    // Pinning them by content, not only by count, is what makes this strong:
    // if the collapse ever dropped one breakpoint's copy and duplicated the
    // other, or if the desktop cell silently regained the prefix and the
    // truncation with it, one of these two assertions fails.
    render(<ReviewPage />);

    const phoneCopies = await screen.findAllByText(
      "Operator: adit@balizero.com",
    );
    expect(phoneCopies).toHaveLength(1);
    expect(screen.getAllByText("Operator: unassigned")).toHaveLength(1);

    const deskCopies = screen.getAllByText("adit@balizero.com");
    expect(deskCopies).toHaveLength(1);
    expect(screen.getAllByText("unassigned")).toHaveLength(1);

    // And each sits behind the media query that belongs to it.
    const sig = (el: HTMLElement) =>
      `${el.className} ${el.parentElement?.className ?? ""}`;
    expect(sig(deskCopies[0])).toContain("max-md:hidden");
    expect(/(?:^|\s)md:hidden(?:\s|$)/.test(sig(phoneCopies[0]))).toBe(true);
    expect(sig(phoneCopies[0])).not.toContain("max-md:hidden");
  });

  it("paints copper only when the viewer received the document, because an admin's queue is global", async () => {
    // Synthetic identities only (no real names / PII, per CLAUDE.md §4).
    // The viewer is an ADMIN — the backend's GET /queue docstring says an
    // admin's queue is GLOBAL, so the response below legitimately includes
    // a row this admin did NOT receive. The law under test: seeing it is
    // not the same as owning it, so it must NEVER paint copper.
    const VIEWER_EMAIL = "member@example.test";
    const baseRow = {
      doc_type: "kitas",
      decision: "NO_MATCH",
      source: "whatsapp",
      status: "review_pending",
      entity_candidates: [],
      extracted_fields: {},
      created_at: "2026-06-15T09:00:00Z",
    };
    // Guilt and innocence on the IDENTICAL record shape — only received_by
    // differs.
    const ownRow = { ...baseRow, proposal_id: 901, received_by: VIEWER_EMAIL };
    const otherRow = {
      ...baseRow,
      proposal_id: 902,
      received_by: "other@example.test",
    };

    getUserProfileMock.mockReturnValue({ email: VIEWER_EMAIL, role: "admin" });
    apiMock.get.mockImplementation(async (endpoint: string) => {
      if (endpoint.startsWith("/api/intake/review/queue")) {
        return { items: [ownRow, otherRow] };
      }
      if (endpoint === "/api/intake/review/document-categories") {
        return { items: [] };
      }
      throw new Error(`Unexpected GET ${endpoint}`);
    });

    render(<ReviewPage />);

    // Innocence: the viewer's OWN record paints copper, "Needs you" —
    // exactly the row-pill count for the ONE owned row (desktop + phone
    // copy), excluding the "Needs you" FILTER chip (a <button>).
    const needsYou = (await screen.findAllByText("Needs you")).filter(
      (el) => el.tagName !== "BUTTON",
    );
    expect(needsYou).toHaveLength(2);

    // Guilt: the identical record received by someone else is muted,
    // "Another operator" — never copper, even though this admin's global
    // queue legitimately shows it.
    expect(screen.getAllByText("Another operator")).toHaveLength(2);

    // The SAME law one typographic level up. The masthead sentence is a
    // claim of ownership, so it counts what the viewer owns, not what
    // loaded. Two rows arrived and exactly one is this admin's, so the
    // sentence must say so. Before this pin it read "2 documents are
    // waiting for your decision" directly above a row the page itself
    // marked "Another operator" — a masthead contradicting its own ledger.
    expect(
      screen.getByText("1 of 2 documents is waiting for your decision."),
    ).toBeVisible();
  });

  it("leads a NO_MATCH proposal with a 'Create new client' CTA prefilled from the extracted fields", async () => {
    render(<ReviewPage />);

    // Open the NO_MATCH proposal (the second card has no proposed client).
    const reviewButtons = await screen.findAllByRole("button", {
      name: "Review",
    });
    // The NO_MATCH row is the one whose reason line reads "No client matched".
    // Re-pinned with the 390px copy cut (SAETTA-R19K K2b): CellStack truncates
    // its secondary, so the longer sentence rendered on a phone as
    // "No client matched — needs a d…". The call to act moved to the copper pill, which
    // is asserted separately, so this still pins the REASON and the pill test
    // still pins the WORD — neither half can vanish unnoticed.
    expect(screen.getByText("No client matched")).toBeVisible();
    // The WORD the pill carries — excluding the "Needs you" FILTER chip
    // (a <button>), which is a different element than the row's own <span>
    // pill and always renders regardless of this row's state.
    expect(
      screen.getAllByText("Needs you").filter((el) => el.tagName !== "BUTTON"),
    ).toHaveLength(2);
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
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Review" }))[0],
    );

    // Read-only notice is shown — AND, per CURE 2, the modal's own title
    // pill now reuses the same reason word, so the text is legitimately in
    // the DOM twice (the Notice banner and the pill).
    const readOnlyNodes = await screen.findAllByText(
      /already filed — view only/i,
    );
    expect(readOnlyNodes).toHaveLength(2);
    for (const node of readOnlyNodes) expect(node).toBeVisible();
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
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Review" }))[0],
    );

    // Per CURE 2, the modal's title pill reuses the same reason word as the
    // Notice banner, so this legitimately matches twice.
    const readOnlyNodes = await screen.findAllByText(
      /claimed by another reviewer — view only/i,
    );
    expect(readOnlyNodes).toHaveLength(2);
    for (const node of readOnlyNodes) expect(node).toBeVisible();
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
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Review" }))[0],
    );

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
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Review" }))[0],
    );

    expect(
      await screen.findByText("Could not open the document."),
    ).toBeVisible();
    // The detail GET failed before any claim attempt.
    expect(apiMock.post).not.toHaveBeenCalled();
  });
});

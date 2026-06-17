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
});

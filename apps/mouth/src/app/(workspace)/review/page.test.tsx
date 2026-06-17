import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReviewPage from "./page";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getToken: vi.fn(() => null),
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
  });

  it("shows the receiving operator on each review card", async () => {
    render(<ReviewPage />);

    expect(
      await screen.findByText("Operator: adit@balizero.com"),
    ).toBeVisible();
    expect(screen.getByText("Operator: unassigned")).toBeVisible();
  });

  it("keeps a manually switched Profile group instead of snapping back", async () => {
    const user = userEvent.setup();
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
        return {
          items: [
            {
              code: "passport",
              name: "Passport",
              category_group: "immigration",
            },
            { code: "nib", name: "NIB", category_group: "pma" },
          ],
        };
      }
      if (endpoint === "/api/intake/review/1") {
        return {
          proposal_id: 1,
          doc_type: "passport",
          decision: "AUTO_ATTACH",
          source: "whatsapp",
          status: "review_pending",
          received_by: "adit@balizero.com",
          entity_candidates: [{ client_id: 21, full_name: "Client One" }],
          extracted_fields: {},
          created_at: "2026-06-15T09:00:00Z",
          routing: null,
        };
      }
      if (endpoint.startsWith("/api/intake/review/clients/")) {
        return { items: [] };
      }
      throw new Error(`Unexpected GET ${endpoint}`);
    });
    apiMock.post.mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/intake/review/1/claim") {
        return {
          proposal_id: 1,
          claim_token: "tok-1",
          lease_expires_at: "2026-06-15T09:15:00Z",
        };
      }
      return {};
    });

    render(<ReviewPage />);

    await user.click(await screen.findByRole("button", { name: "Review" }));

    // Passport auto-infers Immigration on open (auto-inference must still work).
    const groupSelect = (await screen.findByLabelText(
      "Profile group",
    )) as HTMLSelectElement;
    await waitFor(() => expect(groupSelect.value).toBe("immigration"));

    // Manually switch to Company (pma) — must STICK, not snap back.
    await user.selectOptions(groupSelect, "pma");
    expect(groupSelect.value).toBe("pma");

    // The Category dropdown must repopulate for the new group.
    const categorySelect = (await screen.findByLabelText(
      "Category",
    )) as HTMLSelectElement;
    expect(
      within(categorySelect).getByRole("option", { name: "NIB" }),
    ).toBeInTheDocument();

    // Give the (now ref-guarded) re-inference effect a chance to misbehave;
    // the group must remain on the manual choice, never revert.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(groupSelect.value).toBe("pma");
  });
});

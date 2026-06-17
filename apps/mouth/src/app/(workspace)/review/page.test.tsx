import { render, screen } from "@testing-library/react";
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
});

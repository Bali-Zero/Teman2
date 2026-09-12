import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/error-handler";

import ObligationsPage from "./page";

const pushMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
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

const PROPOSED_ROW = {
  id: 101,
  client_id: 42,
  rule_id: "pph21_monthly",
  period_key: "2026-09",
  due_date: "2026-10-10",
  status: "proposed",
  needs_review_reason: "New rule matched",
  reviewer_email: null,
  reviewed_at: null,
  review_note: null,
  alert_id: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const NOVEMBER_ROW = {
  ...PROPOSED_ROW,
  id: 102,
  rule_id: "ppn_monthly",
  period_key: "2026-10",
  due_date: "2026-11-30",
};

const LIST_RESPONSE = {
  total: 1,
  limit: 50,
  offset: 0,
  items: [PROPOSED_ROW],
};

/** Two rows from the catalog M3 serves; the page must never hardcode these. */
const CATALOG = [
  {
    id: "pph21_monthly",
    name: "PPh 21 — employee withholding deposit",
    authority: "DJP",
    legal_source: "PMK 81/2024 art. 94 (pajak.go.id)",
    verified: true,
    frequency: "monthly",
    roll: "next_business_day",
    needs_review_reason: null,
    trigger: null,
    notes: "Deposit by the 15th of the following month.",
  },
  {
    id: "ppn_monthly",
    name: "PPN — monthly VAT return",
    authority: "DJP",
    legal_source: "UU PPN (verify)",
    verified: false,
    frequency: "monthly",
    roll: "next_business_day",
    needs_review_reason:
      "Filing deadline not confirmed against a primary source",
    trigger: null,
    notes: null,
  },
];

/** Synthetic names — no real client appears in this fixture. */
const CLIENT_NAMES: Record<string, string> = {
  "42": "Fixture Client Alpha",
  "43": "Fixture Client Beta",
};

interface Deferred {
  status: string;
  resolve: (total: number) => void;
}

/**
 * URL-dispatching `api.get`: the screen now issues four different reads (list,
 * catalog, the four `limit=1` counters, and one CRM client read per id), so a
 * single blanket mockResolvedValue cannot serve them.
 */
function installApiGet(
  opts: {
    list?: unknown;
    listForClient?: unknown;
    catalog?: unknown;
    clientFails?: boolean;
    counterTotals?: Record<string, number>;
    deferCounters?: Deferred[];
    /** Collects one resolver per CRM client read instead of answering at once. */
    deferClients?: Array<{ id: string; resolve: () => void }>;
  } = {},
) {
  const listCalls: string[] = [];
  const counterCalls: string[] = [];
  const clientCalls: string[] = [];

  apiMock.get.mockImplementation((url: string) => {
    if (url.startsWith("/api/compliance/obligations/catalog")) {
      return Promise.resolve(opts.catalog ?? CATALOG);
    }
    if (url.startsWith("/api/compliance/obligations?")) {
      const params = new URLSearchParams(url.split("?")[1] ?? "");
      if (params.get("limit") === "1") {
        const status = params.get("status") ?? "";
        counterCalls.push(url);
        if (opts.deferCounters) {
          return new Promise((resolve) => {
            opts.deferCounters?.push({
              status,
              resolve: (total: number) =>
                resolve({ total, limit: 1, offset: 0, items: [] }),
            });
          });
        }
        return Promise.resolve({
          total: opts.counterTotals?.[status] ?? 0,
          limit: 1,
          offset: 0,
          items: [],
        });
      }
      listCalls.push(url);
      const body =
        params.get("client_id") && opts.listForClient
          ? opts.listForClient
          : (opts.list ?? LIST_RESPONSE);
      return Promise.resolve(body);
    }
    if (url.startsWith("/api/crm/clients/")) {
      clientCalls.push(url);
      if (opts.clientFails) {
        return Promise.reject(
          new ApiError("Client not found", 404, { detail: "Client not found" }),
        );
      }
      const id = url.slice("/api/crm/clients/".length);
      if (opts.deferClients) {
        return new Promise((resolve) => {
          opts.deferClients?.push({
            id,
            resolve: () =>
              resolve({ id: Number(id), full_name: CLIENT_NAMES[id] ?? null }),
          });
        });
      }
      return Promise.resolve({
        id: Number(id),
        full_name: CLIENT_NAMES[id] ?? null,
      });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });

  return { listCalls, counterCalls, clientCalls };
}

describe("ObligationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    installApiGet();
    apiMock.post.mockResolvedValue({});
  });

  it("renders proposed rows from the list response", async () => {
    render(<ObligationsPage />);

    expect(
      await screen.findByText("PPh 21 — employee withholding deposit"),
    ).toBeVisible();
    expect(screen.getByText("2026-09")).toBeVisible();
    expect(screen.getByText("2026-10-10")).toBeVisible();
    expect(screen.getByText("New rule matched")).toBeVisible();
    // "proposed" also appears as the status-filter default option and as a
    // counter label, so assert presence (>=1) rather than uniqueness.
    expect(screen.getAllByText("proposed").length).toBeGreaterThan(0);
    expect(screen.getByText("101")).toBeVisible();
    // The rule id stays visible under the name: the reviewer still needs it to
    // talk to the engine.
    expect(screen.getByText("pph21_monthly")).toBeVisible();

    expect(apiMock.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/compliance/obligations?"),
    );
    expect(apiMock.get).toHaveBeenCalledWith(
      expect.stringContaining("status=proposed"),
    );
  });

  it("labels each rule with its catalog name, authority and verified badge", async () => {
    installApiGet({
      list: {
        total: 2,
        limit: 50,
        offset: 0,
        items: [PROPOSED_ROW, NOVEMBER_ROW],
      },
    });
    render(<ObligationsPage />);

    await screen.findByText("PPh 21 — employee withholding deposit");
    expect(screen.getByText("PPN — monthly VAT return")).toBeVisible();
    expect(screen.getByText("verified")).toBeVisible();
    expect(screen.getByText("unverified")).toBeVisible();
    expect(screen.getAllByText("DJP").length).toBe(2);

    expect(apiMock.get).toHaveBeenCalledWith(
      "/api/compliance/obligations/catalog",
    );
    // Catalog read is once per mount, not once per row.
    expect(
      apiMock.get.mock.calls.filter(
        (call: unknown[]) => call[0] === "/api/compliance/obligations/catalog",
      ).length,
    ).toBe(1);
  });

  it("shows legal_source in the row detail", async () => {
    render(<ObligationsPage />);
    await screen.findByText("PPh 21 — employee withholding deposit");

    expect(
      screen.queryByText("PMK 81/2024 art. 94 (pajak.go.id)"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Rule detail for obligation 101"));

    expect(
      await screen.findByText("PMK 81/2024 art. 94 (pajak.go.id)"),
    ).toBeVisible();
    expect(screen.getByText("Legal source")).toBeVisible();
  });

  it("resolves the client id to a display name through the CRM read", async () => {
    render(<ObligationsPage />);

    expect(await screen.findByText("Fixture Client Alpha")).toBeVisible();
    expect(screen.getByText("#42")).toBeVisible();
    expect(apiMock.get).toHaveBeenCalledWith("/api/crm/clients/42");
  });

  it("falls back to the client id when the CRM read fails", async () => {
    installApiGet({ clientFails: true });
    render(<ObligationsPage />);

    await screen.findByText("PPh 21 — employee withholding deposit");
    await waitFor(() =>
      expect(apiMock.get).toHaveBeenCalledWith("/api/crm/clients/42"),
    );

    expect(screen.queryByText("Fixture Client Alpha")).not.toBeInTheDocument();
    expect(screen.getByText("42")).toBeVisible();
  });

  it("keeps a name resolution that lands after the rows changed", async () => {
    // Regression: ids are marked attempted when the read STARTS, so a cleanup
    // that discarded in-flight results (rows changed while the read was open)
    // left those ids permanently stuck on the id fallback.
    const deferClients: Array<{ id: string; resolve: () => void }> = [];
    installApiGet({
      deferClients,
      listForClient: {
        total: 1,
        limit: 50,
        offset: 0,
        items: [{ ...PROPOSED_ROW, id: 103, client_id: 43 }],
      },
    });

    render(<ObligationsPage />);
    await waitFor(() => expect(deferClients.length).toBe(1));
    expect(deferClients[0].id).toBe("42");

    // Rows change while client 42's read is still open: the effect re-runs for
    // the new id set and React cleans up the previous run.
    fireEvent.change(screen.getByPlaceholderText("all clients"), {
      target: { value: "43" },
    });
    await waitFor(() => expect(deferClients.length).toBe(2));

    // Back to the first id set. 42 is already attempted, so no second read.
    fireEvent.change(screen.getByPlaceholderText("all clients"), {
      target: { value: "" },
    });
    deferClients.forEach((d) => d.resolve());

    expect(await screen.findByText("Fixture Client Alpha")).toBeVisible();
    expect(
      apiMock.get.mock.calls.filter(
        (call: unknown[]) => call[0] === "/api/crm/clients/42",
      ).length,
    ).toBe(1);
  });

  it("reads one counter per status with limit=1, all four in parallel", async () => {
    const deferred: Deferred[] = [];
    const { counterCalls } = installApiGet({ deferCounters: deferred });

    render(<ObligationsPage />);

    // All four reads are dispatched before any of them resolves.
    await waitFor(() => expect(deferred.length).toBe(4));
    expect(counterCalls.every((url) => url.includes("limit=1"))).toBe(true);
    expect(deferred.map((d) => d.status).sort()).toEqual([
      "alerted",
      "approved",
      "proposed",
      "rejected",
    ]);

    const totals: Record<string, number> = {
      proposed: 7,
      approved: 3,
      rejected: 1,
      alerted: 2,
    };
    deferred.forEach((d) => d.resolve(totals[d.status] ?? 0));

    // waitFor, not findByTestId: the tiles already exist (showing the loading
    // placeholder), so findBy* would resolve before the totals land and assert
    // against the placeholder.
    await waitFor(() => {
      expect(screen.getByTestId("counter-proposed")).toHaveTextContent("7");
      expect(screen.getByTestId("counter-approved")).toHaveTextContent("3");
      expect(screen.getByTestId("counter-rejected")).toHaveTextContent("1");
      expect(screen.getByTestId("counter-alerted")).toHaveTextContent("2");
    });
  });

  it("clears the counters when the client filter changes", async () => {
    // Regression: holding the previous filter's totals while the new reads are
    // in flight showed one client's counts under another client's label.
    const deferred: Deferred[] = [];
    installApiGet({ deferCounters: deferred, listForClient: LIST_RESPONSE });

    render(<ObligationsPage />);
    await waitFor(() => expect(deferred.length).toBe(4));
    deferred.forEach((d) => d.resolve(9));
    await waitFor(() =>
      expect(screen.getByTestId("counter-proposed")).toHaveTextContent("9"),
    );

    deferred.length = 0;
    fireEvent.change(screen.getByPlaceholderText("all clients"), {
      target: { value: "42" },
    });

    await waitFor(() =>
      expect(screen.getByTestId("counter-proposed")).not.toHaveTextContent("9"),
    );
    expect(screen.getByText("Client 42")).toBeVisible();
  });

  it("reads the catalog once and renders it under StrictMode", async () => {
    // Regression: `reactStrictMode` is on, so React runs setup -> cleanup ->
    // setup in dev. A boolean "already started" guard let the first run fetch,
    // the cleanup discard the result, and the second run bail out — an empty
    // catalog with no request left to recover it.
    render(
      <StrictMode>
        <ObligationsPage />
      </StrictMode>,
    );

    expect(
      await screen.findByText("PPh 21 — employee withholding deposit"),
    ).toBeVisible();
    expect(
      apiMock.get.mock.calls.filter(
        (call: unknown[]) => call[0] === "/api/compliance/obligations/catalog",
      ).length,
    ).toBe(1);
  });

  it("groups rows by due month only when a client filter is set", async () => {
    installApiGet({
      listForClient: {
        total: 2,
        limit: 50,
        offset: 0,
        items: [PROPOSED_ROW, NOVEMBER_ROW],
      },
    });
    render(<ObligationsPage />);

    await screen.findByText("PPh 21 — employee withholding deposit");
    expect(screen.queryByText("October 2026")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("all clients"), {
      target: { value: "42" },
    });

    expect(await screen.findByText("October 2026")).toBeVisible();
    expect(screen.getByText("November 2026")).toBeVisible();
    expect(apiMock.get).toHaveBeenCalledWith(
      expect.stringContaining("client_id=42"),
    );
  });

  it("approve sends the note and refetches the list", async () => {
    const { listCalls } = installApiGet();
    apiMock.post.mockResolvedValueOnce({
      obligation: { ...PROPOSED_ROW, status: "alerted" },
      alert_id: "alert_obligation_42_abcd1234",
    });

    render(<ObligationsPage />);
    await screen.findByText("PPh 21 — employee withholding deposit");

    const noteInput = screen.getByLabelText("Note for obligation 101");
    fireEvent.change(noteInput, { target: { value: "looks correct" } });

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/compliance/obligations/101/approve",
        { note: "looks correct" },
      );
    });

    // Refetch: the initial load + the post-approve reload.
    await waitFor(() => expect(listCalls.length).toBe(2));

    expect(
      await screen.findByText(
        "✓ Obligation #101 approved → alert alert_obligation_42_abcd1234.",
      ),
    ).toBeVisible();
  });

  it("reject requires a reason and is disabled without one", async () => {
    render(<ObligationsPage />);
    await screen.findByText("PPh 21 — employee withholding deposit");

    const rejectBtn = screen.getByRole("button", { name: "Reject" });
    fireEvent.click(rejectBtn);

    expect(
      await screen.findByText("A reason is required to reject."),
    ).toBeVisible();
    expect(apiMock.post).not.toHaveBeenCalled();

    const noteInput = screen.getByLabelText("Note for obligation 101");
    fireEvent.change(noteInput, { target: { value: "duplicate rule" } });
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/compliance/obligations/101/reject",
        { reason: "duplicate rule" },
      );
    });
  });

  it("generate with needs_manual_classification=true shows the warning banner", async () => {
    apiMock.post.mockResolvedValueOnce({
      client_id: 42,
      inserted_count: 3,
      company_type: "OTHER",
      needs_manual_classification: true,
      warning:
        "profile_from_rows could not map this client's company_type to a known type",
      rows: [],
    });

    render(<ObligationsPage />);
    await screen.findByText("PPh 21 — employee withholding deposit");

    fireEvent.change(screen.getByPlaceholderText("e.g. 42"), {
      target: { value: "42" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposals" }));

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        "/api/compliance/obligations/generate",
        { client_id: 42, horizon_days: 90 },
      );
    });

    expect(
      await screen.findByText(/Inserted 3 new proposals for client 42/),
    ).toBeVisible();
    expect(screen.getByText(/company_type to a known type/)).toBeVisible();
  });

  it("shows the admin-only message on a 403", async () => {
    apiMock.get.mockReset();
    apiMock.get.mockRejectedValue(
      new ApiError("CRM admin required", 403, { detail: "CRM admin required" }),
    );

    render(<ObligationsPage />);

    expect(await screen.findByText("Admin only.")).toBeVisible();
    expect(
      screen.getByText("Could not load the rule catalog — showing rule ids."),
    ).toBeVisible();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchActions, fetchOwners, patchAction } from "./wa-actions-api";
import type { ActionQueueRow } from "@/types/wa-action";

const action: ActionQueueRow = {
  action_id: 17,
  client_id: 2,
  practice_id: 3,
  conversation_id: 4,
  action_type: "follow_up",
  reason: "Client needs an update",
  recommended_action: "Reply",
  suggested_message_draft: "We are checking this now.",
  due_at: "2026-07-19T00:00:00Z",
  evidence: { source: "whatsapp" },
  owner: "ops",
  priority: 90,
  status: "open",
  snoozed_until: null,
  dismiss_reason: null,
  resolution_notes: null,
  created_at: "2026-07-18T00:00:00Z",
  resolved_at: null,
  client_full_name: "Example Client",
  practice_kind: "visa",
};

function response(body: unknown, status = 200): Response {
  return new Response(body === undefined ? undefined : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchActions", () => {
  it("encodes supported filters and sends the session cookie", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        response({ items: [action], limit: 25, offset: 50, total: 1 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchActions({
      owner: "ops team",
      status: "open",
      min_priority: 80,
      action_type: "follow/up",
      search: "client + urgent",
      sort: "due_at",
      order: "asc",
      limit: 25,
      offset: 50,
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://dashboard.local");
    expect(parsed.pathname).toBe("/api/wa/actions");
    expect(Object.fromEntries(parsed.searchParams)).toEqual({
      owner: "ops team",
      status: "open",
      min_priority: "80",
      action_type: "follow/up",
      search: "client + urgent",
      sort: "due_at",
      order: "asc",
      limit: "25",
      offset: "50",
    });
    expect(init).toEqual({ credentials: "include" });
    expect(result.items).toEqual([action]);
  });

  it("omits absent and empty filters without leaving a question mark", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        response({ items: [], limit: 50, offset: 0, total: 0 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await fetchActions({ owner: "", status: undefined });

    expect(fetchMock).toHaveBeenCalledWith("/api/wa/actions", {
      credentials: "include",
    });
  });

  it("surfaces the backend error detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ detail: "not authorized" }, 403)),
    );

    await expect(fetchActions({})).rejects.toThrow(
      "fetchActions failed: not authorized",
    );
  });

  it("falls back to the HTTP status when an error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("bad gateway", { status: 502 })),
    );

    await expect(fetchActions({})).rejects.toThrow(
      "fetchActions failed: HTTP 502",
    );
  });

  it("falls back to the HTTP status when JSON has no detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, 429)));

    await expect(fetchActions({})).rejects.toThrow(
      "fetchActions failed: HTTP 429",
    );
  });
});

describe("fetchOwners", () => {
  it("returns owners using an authenticated request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(response({ owners: ["ops", "legal"] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchOwners()).resolves.toEqual({ owners: ["ops", "legal"] });
    expect(fetchMock).toHaveBeenCalledWith("/api/wa/actions/owners", {
      credentials: "include",
    });
  });

  it("reports an HTTP failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, 503)));

    await expect(fetchOwners()).rejects.toThrow("fetchOwners failed: HTTP 503");
  });
});

describe("patchAction", () => {
  it("serializes the patch contract and sends the session cookie", async () => {
    const updated = { ...action, status: "done" as const };
    const fetchMock = vi.fn().mockResolvedValue(response(updated));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      patchAction(17, { status: "done", resolution_notes: "Client replied" }),
    ).resolves.toEqual(updated);
    expect(fetchMock).toHaveBeenCalledWith("/api/wa/actions/17", {
      method: "PATCH",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        status: "done",
        resolution_notes: "Client replied",
      }),
    });
  });

  it("surfaces the backend patch error detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(response({ detail: "invalid transition" }, 409)),
    );

    await expect(patchAction(17, { status: "done" })).rejects.toThrow(
      "patchAction failed: invalid transition",
    );
  });

  it("falls back to the patch HTTP status for malformed error bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 })),
    );

    await expect(patchAction(17, { owner: "ops" })).rejects.toThrow(
      "patchAction failed: HTTP 503",
    );
  });

  it("falls back to the patch HTTP status when JSON has no detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, 422)));

    await expect(patchAction(17, { owner: "ops" })).rejects.toThrow(
      "patchAction failed: HTTP 422",
    );
  });
});

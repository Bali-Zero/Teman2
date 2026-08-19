import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  startCron: vi.fn(),
  createIntent: vi.fn(),
  getPool: vi.fn(),
  insertAuditRow: vi.fn(),
  query: vi.fn(),
}));

vi.mock("@/lib/cockpit-launchctl", () => ({
  startCron: mocks.startCron,
}));

vi.mock("@/lib/cockpit-pg", () => ({
  createIntent: mocks.createIntent,
  insertAuditRow: mocks.insertAuditRow,
}));

vi.mock("@/app/lib/db", () => ({
  getPool: mocks.getPool,
}));

import { POST as runCron } from "@/app/api/cockpit/cron/run/route";
import { POST as createIntent } from "@/app/api/cockpit/intent/create/route";
import {
  GET as getRecommendations,
  PATCH as patchRecommendation,
} from "@/app/api/llm-costs/recommendations/route";
import { createCockpitSessionToken } from "@/lib/cockpit-session";

type Handler = (request: NextRequest) => Promise<Response>;

const SECRET =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
const AUDIENCE = "http://localhost:3100";

function request(
  path: string,
  options: {
    contentType?: string;
    origin?: string;
    secFetchSite?: string;
  },
): NextRequest {
  const headers = new Headers({
    host: "localhost:3100",
    "content-type": options.contentType ?? "application/json",
  });
  if (options.origin !== undefined) headers.set("origin", options.origin);
  if (options.secFetchSite !== undefined) {
    headers.set("sec-fetch-site", options.secFetchSite);
  }
  return new NextRequest(`http://localhost:3100${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify({ deliberately: "invalid business payload" }),
  });
}

function recommendationRequest(
  method: "GET" | "PATCH",
  options: { token?: string; origin?: string } = {},
): NextRequest {
  const headers = new Headers({ host: "localhost:3100" });
  if (options.token) {
    headers.set("authorization", `Bearer ${options.token}`);
  }
  if (method === "PATCH") {
    headers.set("content-type", "application/json");
    headers.set("origin", options.origin ?? AUDIENCE);
    headers.set("sec-fetch-site", "same-origin");
  }
  return new NextRequest(`${AUDIENCE}/api/llm-costs/recommendations`, {
    method,
    headers,
    body:
      method === "PATCH"
        ? JSON.stringify({ id: 7, status: "reviewed" })
        : undefined,
  });
}

describe.each([
  ["cron run", "/api/cockpit/cron/run", runCron],
  ["intent create", "/api/cockpit/intent/create", createIntent],
] as const)("%s mutation boundary", (_name, path, handler: Handler) => {
  beforeEach(() => {
    mocks.startCron.mockReset();
    mocks.createIntent.mockReset();
    mocks.insertAuditRow.mockReset();
  });

  it.each([
    [{ contentType: "text/plain" }, 415],
    [{ origin: "http://localhost:4100" }, 403],
    [{ secFetchSite: "same-site" }, 403],
  ] as const)(
    "rejects %o before business validation",
    async (options, status) => {
      const response = await handler(request(path, options));

      expect(response.status).toBe(status);
      expect(mocks.startCron).not.toHaveBeenCalled();
      expect(mocks.createIntent).not.toHaveBeenCalled();
      expect(mocks.insertAuditRow).not.toHaveBeenCalled();
    },
  );
});

describe("recommendation API session boundary", () => {
  beforeEach(() => {
    process.env.COCKPIT_SESSION_KEY = SECRET;
    mocks.getPool.mockReset().mockResolvedValue({ query: mocks.query });
    mocks.query.mockReset();
  });

  afterEach(() => {
    delete process.env.COCKPIT_SESSION_KEY;
  });

  it("rejects anonymous GET and PATCH before touching the database", async () => {
    const getResponse = await getRecommendations(recommendationRequest("GET"));
    const patchResponse = await patchRecommendation(
      recommendationRequest("PATCH"),
    );

    expect(getResponse.status).toBe(401);
    expect(patchResponse.status).toBe(401);
    expect(mocks.getPool).not.toHaveBeenCalled();
    expect(mocks.query).not.toHaveBeenCalled();
  });

  it("keeps authenticated GET and PATCH functional", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);
    mocks.query
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rowCount: 1 });

    const getResponse = await getRecommendations(
      recommendationRequest("GET", { token }),
    );
    const patchResponse = await patchRecommendation(
      recommendationRequest("PATCH", { token }),
    );

    expect(getResponse.status).toBe(200);
    expect(patchResponse.status).toBe(200);
    expect(mocks.getPool).toHaveBeenCalledTimes(2);
    expect(mocks.query).toHaveBeenLastCalledWith(
      expect.stringContaining("UPDATE llm_cost_recommendations"),
      [7, "reviewed"],
    );
  });

  it("rejects an authenticated cross-origin PATCH before the database", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE);

    const response = await patchRecommendation(
      recommendationRequest("PATCH", {
        token,
        origin: "http://localhost:4100",
      }),
    );

    expect(response.status).toBe(403);
    expect(mocks.getPool).not.toHaveBeenCalled();
    expect(mocks.query).not.toHaveBeenCalled();
  });
});

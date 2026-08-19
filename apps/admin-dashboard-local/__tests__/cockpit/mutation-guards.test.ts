import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  startCron: vi.fn(),
  createIntent: vi.fn(),
  insertAuditRow: vi.fn(),
}));

vi.mock("@/lib/cockpit-launchctl", () => ({
  startCron: mocks.startCron,
}));

vi.mock("@/lib/cockpit-pg", () => ({
  createIntent: mocks.createIntent,
  insertAuditRow: mocks.insertAuditRow,
}));

import { POST as runCron } from "@/app/api/cockpit/cron/run/route";
import { POST as createIntent } from "@/app/api/cockpit/intent/create/route";

type Handler = (request: NextRequest) => Promise<Response>;

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

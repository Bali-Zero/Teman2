import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  insertAuditRow: vi.fn(),
  readPassphraseHash: vi.fn(),
  verifyPassphrase: vi.fn(),
}));

vi.mock("@/lib/cockpit-pg", () => ({
  insertAuditRow: mocks.insertAuditRow,
}));

vi.mock("@/lib/cockpit-auth", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/cockpit-auth")>(
      "@/lib/cockpit-auth",
    );
  return {
    ...actual,
    readPassphraseHash: mocks.readPassphraseHash,
    verifyPassphrase: mocks.verifyPassphrase,
  };
});

import { POST } from "@/app/api/cockpit/auth/route";
import { isLockedOut, resetRateLimit } from "@/lib/cockpit-auth";
import {
  COCKPIT_SESSION_MAX_AGE_SECONDS,
  verifyCockpitSessionToken,
} from "@/lib/cockpit-session";

const SECRET =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
const VALID_PASSPHRASE = "synthetic-valid-passphrase-2026";

function request(
  options: {
    passphrase?: string;
    contentType?: string;
    origin?: string;
    secFetchSite?: string;
    forwardedFor?: string;
  } = {},
): NextRequest {
  const headers = new Headers({
    host: "localhost:3100",
    "content-type": options.contentType ?? "application/json; charset=utf-8",
  });
  if (options.origin !== undefined) headers.set("origin", options.origin);
  if (options.secFetchSite !== undefined) {
    headers.set("sec-fetch-site", options.secFetchSite);
  }
  if (options.forwardedFor !== undefined) {
    headers.set("x-forwarded-for", options.forwardedFor);
  }
  return new NextRequest("http://localhost:3100/api/cockpit/auth", {
    method: "POST",
    headers,
    body: JSON.stringify({
      passphrase: options.passphrase ?? "synthetic-invalid-passphrase-2026",
    }),
  });
}

describe("cockpit auth route boundary", () => {
  beforeEach(() => {
    process.env.COCKPIT_HMAC_KEY = SECRET;
    resetRateLimit();
    mocks.insertAuditRow.mockReset().mockResolvedValue(1n);
    mocks.readPassphraseHash.mockReset().mockReturnValue("synthetic-hash");
    mocks.verifyPassphrase
      .mockReset()
      .mockImplementation(async (passphrase: string) =>
        Promise.resolve(passphrase === VALID_PASSPHRASE),
      );
  });

  afterEach(() => {
    delete process.env.COCKPIT_HMAC_KEY;
    resetRateLimit();
  });

  it("returns an ephemeral signed token without setting a cookie", async () => {
    const response = await POST(
      request({
        passphrase: VALID_PASSPHRASE,
        origin: "http://localhost:3100",
        secFetchSite: "same-origin",
      }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toBeNull();
    const body = (await response.json()) as {
      token: string;
      expires_in: number;
    };
    expect(body.expires_in).toBe(COCKPIT_SESSION_MAX_AGE_SECONDS);
    expect(await verifyCockpitSessionToken(body.token, SECRET)).toBe(true);
    expect(mocks.insertAuditRow).toHaveBeenCalledWith(
      SECRET,
      expect.objectContaining({
        action: "auth.passphrase",
        params: {},
        result: "success",
      }),
    );
    expect(JSON.stringify(mocks.insertAuditRow.mock.calls)).not.toContain(
      VALID_PASSPHRASE,
    );
  });

  it("bounds parallel bcrypt work at the global failure limit", async () => {
    const resolvers: Array<(accepted: boolean) => void> = [];
    mocks.verifyPassphrase.mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          resolvers.push(resolve);
        }),
    );

    const attempts = Array.from({ length: 7 }, (_, index) =>
      POST(request({ forwardedFor: `198.51.100.${index + 1}` })),
    );
    await vi.waitFor(() =>
      expect(mocks.verifyPassphrase).toHaveBeenCalledTimes(5),
    );
    for (const resolve of resolvers) resolve(false);

    const responses = await Promise.all(attempts);
    expect(
      responses.filter((response) => response.status === 401),
    ).toHaveLength(5);
    expect(
      responses.filter((response) => response.status === 429),
    ).toHaveLength(2);
    expect(isLockedOut()).toBe(true);
  });

  it("uses one global bucket even when X-Forwarded-For rotates", async () => {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const response = await POST(
        request({ forwardedFor: `198.51.100.${attempt + 1}` }),
      );
      expect(response.status).toBe(401);
    }

    const locked = await POST(request({ forwardedFor: "203.0.113.250" }));
    expect(locked.status).toBe(429);
    expect(mocks.verifyPassphrase).toHaveBeenCalledTimes(5);
  });

  it("rejects non-JSON and cross-site browser signals before parsing", async () => {
    const wrongType = await POST(request({ contentType: "text/plain" }));
    const crossOrigin = await POST(
      request({ origin: "http://localhost:4100" }),
    );
    const crossSite = await POST(request({ secFetchSite: "same-site" }));

    expect(wrongType.status).toBe(415);
    expect(crossOrigin.status).toBe(403);
    expect(crossSite.status).toBe(403);
    expect(mocks.verifyPassphrase).not.toHaveBeenCalled();
    expect(mocks.insertAuditRow).not.toHaveBeenCalled();
  });

  it("records the memory failure before waiting for audit I/O", async () => {
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await POST(request());
    }

    let finishAudit: (() => void) | undefined;
    mocks.insertAuditRow.mockImplementationOnce(
      () =>
        new Promise<bigint>((resolve) => {
          finishAudit = () => resolve(1n);
        }),
    );
    const fifth = POST(request());
    await vi.waitFor(() => expect(isLockedOut()).toBe(true));
    finishAudit?.();
    expect((await fifth).status).toBe(401);
  });

  it("keeps denials denied but fails closed on a success audit outage", async () => {
    mocks.insertAuditRow.mockRejectedValue(new Error("synthetic audit outage"));
    const denied = await POST(request());
    expect(denied.status).toBe(401);

    resetRateLimit();
    const acceptedWithoutAudit = await POST(
      request({ passphrase: VALID_PASSPHRASE }),
    );
    expect(acceptedWithoutAudit.status).toBe(503);
    expect(await acceptedWithoutAudit.json()).toEqual({
      error: "audit_unavailable",
    });
    expect(acceptedWithoutAudit.headers.get("set-cookie")).toBeNull();
  });
});

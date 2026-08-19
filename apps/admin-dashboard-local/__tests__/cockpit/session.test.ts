import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";
import {
  createCockpitSessionToken,
  hasValidCockpitSession,
  verifyCockpitSessionToken,
} from "@/lib/cockpit-session";
import { cockpitHostname, isAllowedCockpitHost } from "@/lib/cockpit-host";

const SECRET =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
const NOW = Date.UTC(2026, 7, 19, 8, 0, 0);
const AUDIENCE = "http://localhost:3100";

function request(
  pathname: string,
  options: {
    host?: string;
    token?: string;
    cookieToken?: string;
    extraAuthorization?: string;
    requestOrigin?: string;
  } = {},
): NextRequest {
  const requestOrigin = options.requestOrigin ?? AUDIENCE;
  const headers = new Headers({
    host: options.host ?? new URL(requestOrigin).host,
  });
  if (options.token) {
    headers.set("authorization", `Bearer ${options.token}`);
  }
  if (options.extraAuthorization) {
    headers.append("authorization", options.extraAuthorization);
  }
  if (options.cookieToken) {
    headers.set("cookie", `cockpit-session=${options.cookieToken}`);
  }
  return new NextRequest(`${requestOrigin}${pathname}`, { headers });
}

describe("cockpit signed session", () => {
  beforeEach(() => {
    process.env.COCKPIT_SESSION_KEY = SECRET;
  });

  afterEach(() => {
    delete process.env.COCKPIT_SESSION_KEY;
  });

  it("accepts a valid, unexpired token", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nowMs: NOW,
      nonce: "fixed-synthetic-nonce",
    });
    expect(
      await verifyCockpitSessionToken(token, SECRET, AUDIENCE, NOW + 1_000),
    ).toBe(true);
  });

  it("rejects missing, forged, and expired tokens", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nowMs: NOW,
      maxAgeSeconds: 60,
      nonce: "fixed-synthetic-nonce",
    });
    const forged = `${token.slice(0, -1)}${token.endsWith("A") ? "B" : "A"}`;

    expect(await verifyCockpitSessionToken(null, SECRET, AUDIENCE, NOW)).toBe(
      false,
    );
    expect(await verifyCockpitSessionToken(forged, SECRET, AUDIENCE, NOW)).toBe(
      false,
    );
    expect(
      await verifyCockpitSessionToken(token, SECRET, AUDIENCE, NOW + 60_000),
    ).toBe(false);
  });

  it("middleware rejects protected APIs without a valid token", async () => {
    const missing = await middleware(request("/api/garuda-voa/evaluate"));
    const forged = await middleware(
      request("/api/garuda-voa/evaluate", { token: "forged.value" }),
    );
    expect(missing.status).toBe(401);
    expect(forged.status).toBe(401);
  });

  it("rejects a valid token presented only as a cookie", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nonce: "fixed-synthetic-nonce",
    });
    const cookieOnly = request("/api/garuda-voa/evaluate", {
      host: "localhost:4100",
      cookieToken: token,
    });
    expect(await hasValidCockpitSession(cookieOnly)).toBe(false);
    expect((await middleware(cookieOnly)).status).toBe(401);
  });

  it("rejects malformed and multiple Authorization credentials", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nonce: "fixed-synthetic-nonce",
    });
    expect(
      await hasValidCockpitSession(
        request("/api/cockpit/session", { token: "not-a-signed-token" }),
      ),
    ).toBe(false);
    expect(
      await hasValidCockpitSession(
        request("/api/cockpit/session", {
          token,
          extraAuthorization: `Bearer ${token}`,
        }),
      ),
    ).toBe(false);
  });

  it("middleware accepts a valid token and applies private headers", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nonce: "fixed-synthetic-nonce",
    });
    const response = await middleware(
      request("/api/garuda-voa/evaluate", { token }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toContain("no-store");
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
  });

  it("host gate is fail-closed even with a valid token", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nonce: "fixed-synthetic-nonce",
    });
    const response = await middleware(
      request("/api/garuda-voa/evaluate", {
        host: "cockpit.example.com",
        token,
      }),
    );
    expect(response.status).toBe(403);
  });

  it("binds a signed token to the exact origin including port", async () => {
    const token = await createCockpitSessionToken(SECRET, AUDIENCE, {
      nonce: "fixed-synthetic-nonce",
    });

    expect(
      await verifyCockpitSessionToken(token, SECRET, "http://localhost:4100"),
    ).toBe(false);
    expect(
      await hasValidCockpitSession(
        request("/api/cockpit/session", {
          token,
          requestOrigin: "http://localhost:4100",
        }),
      ),
    ).toBe(false);
  });
});

describe("cockpit host parsing", () => {
  it("accepts only loopback hostnames with optional ports", () => {
    expect(isAllowedCockpitHost("localhost:3100")).toBe(true);
    expect(isAllowedCockpitHost("127.0.0.1:3100")).toBe(true);
    expect(isAllowedCockpitHost("[::1]:3100")).toBe(true);
    expect(cockpitHostname("[::1]:3100")).toBe("[::1]");
  });

  it("rejects malformed, forwarded, and remote hosts", () => {
    expect(isAllowedCockpitHost(null)).toBe(false);
    expect(isAllowedCockpitHost("localhost, attacker.example")).toBe(false);
    expect(isAllowedCockpitHost("100.107.22.111:3100")).toBe(false);
    expect(isAllowedCockpitHost("localhost:bad")).toBe(false);
  });
});

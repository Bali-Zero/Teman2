import assert from "node:assert/strict";
import test from "node:test";

import {
  assertBackendHealthy,
  isDisallowedNetworkRequest,
  isUnsafeWriteRequest,
  loadProdlikeEnvironment,
  ProdlikePreflightError,
  REQUIRED_SYNTHETIC_CONTRACTS,
  type EnvironmentSource,
} from "./prodlike-preflight.ts";

const SYNTHETIC_SECRET_SENTINEL = "must-not-appear-in-diagnostics";

function safeEnvironment(): Record<string, string> {
  const environment = Object.fromEntries(
    REQUIRED_SYNTHETIC_CONTRACTS.map((name) => [name, `synthetic-${name}`]),
  );
  environment.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL = "portal-smoke@example.test";
  environment.MY_PORTAL_SYNTHETIC_CLIENT_PIN = SYNTHETIC_SECRET_SENTINEL;
  environment.NUZANTARA_API_URL = "http://127.0.0.1:8000";
  environment.MY_PORTAL_BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health";
  return environment;
}

function capturePreflightError(environment: EnvironmentSource): string {
  try {
    loadProdlikeEnvironment(environment);
  } catch (error) {
    assert.ok(error instanceof ProdlikePreflightError);
    return error.message;
  }
  assert.fail("Expected the prod-like preflight to fail closed");
}

test("missing contracts fail closed with names only", () => {
  const environment = safeEnvironment();
  delete environment.MY_PORTAL_SYNTHETIC_TENANT_ID;
  delete environment.MY_PORTAL_EXTERNAL_SIDE_EFFECT_SINK;

  const message = capturePreflightError(environment);

  assert.match(message, /before browser or network startup/);
  assert.match(message, /MY_PORTAL_SYNTHETIC_TENANT_ID/);
  assert.match(message, /MY_PORTAL_EXTERNAL_SIDE_EFFECT_SINK/);
  assert.doesNotMatch(message, new RegExp(SYNTHETIC_SECRET_SENTINEL));
  assert.doesNotMatch(message, /portal-smoke@example\.test/);
});

test("known production endpoints are rejected without echoing their value", async (t) => {
  for (const productionHost of ["my.balizero.com", "nuzantara-rag.fly.dev"]) {
    await t.test(productionHost, () => {
      const environment = safeEnvironment();
      environment.NUZANTARA_API_URL = `https://${productionHost}`;
      environment.MY_PORTAL_BACKEND_HEALTH_URL = `https://${productionHost}/health`;

      const message = capturePreflightError(environment);

      assert.match(message, /production endpoint is forbidden/);
      assert.ok(!message.includes(productionHost));
      assert.doesNotMatch(message, new RegExp(SYNTHETIC_SECRET_SENTINEL));
    });
  }
});

test("ambiguous bind addresses and loopback URLs without ports are rejected", () => {
  const bindEnvironment = safeEnvironment();
  bindEnvironment.NUZANTARA_API_URL = "http://0.0.0.0:8000";
  bindEnvironment.MY_PORTAL_BACKEND_HEALTH_URL = "http://0.0.0.0:8000/health";
  assert.match(
    capturePreflightError(bindEnvironment),
    /loopback or an explicitly allowlisted/,
  );

  const noPortEnvironment = safeEnvironment();
  noPortEnvironment.NUZANTARA_API_URL = "http://localhost";
  noPortEnvironment.MY_PORTAL_BACKEND_HEALTH_URL = "http://localhost/health";
  assert.match(
    capturePreflightError(noPortEnvironment),
    /require an explicit port/,
  );
});

test("a safe loopback backend configuration passes without network activity", () => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = (() => {
    fetchCalls += 1;
    throw new Error("unexpected network activity");
  }) as typeof fetch;

  try {
    const environment = loadProdlikeEnvironment(safeEnvironment());
    assert.equal(environment.backendApiUrl, "http://127.0.0.1:8000");
    assert.equal(environment.backendHealthUrl, "http://127.0.0.1:8000/health");
    assert.equal(environment.frontendPort, 3101);
    assert.equal(fetchCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("an invalid frontend port fails before any health request", () => {
  const environment = safeEnvironment();
  environment.MY_PORTAL_PRODLIKE_PORT = "not-a-port";

  assert.match(
    capturePreflightError(environment),
    /MY_PORTAL_PRODLIKE_PORT.*unprivileged numeric port/,
  );
});

test("an explicitly allowlisted non-production hostname passes", () => {
  const environment = safeEnvironment();
  environment.MY_PORTAL_PRODLIKE_ALLOWED_HOSTS = "portal-api.qa.example.test";
  environment.NUZANTARA_API_URL = "https://portal-api.qa.example.test/api";
  environment.MY_PORTAL_BACKEND_HEALTH_URL =
    "https://portal-api.qa.example.test/health/ready";

  const parsed = loadProdlikeEnvironment(environment);

  assert.equal(parsed.backendApiUrl, "https://portal-api.qa.example.test");
  assert.equal(
    parsed.backendHealthUrl,
    "https://portal-api.qa.example.test/health/ready",
  );
});

test("a non-allowlisted hostname and a mismatched health origin fail closed", () => {
  const notAllowed = safeEnvironment();
  notAllowed.NUZANTARA_API_URL = "https://portal-api.qa.example.test";
  notAllowed.MY_PORTAL_BACKEND_HEALTH_URL =
    "https://portal-api.qa.example.test/health";
  assert.match(
    capturePreflightError(notAllowed),
    /explicitly allowlisted non-production hostname/,
  );

  const mismatched = safeEnvironment();
  mismatched.MY_PORTAL_PRODLIKE_ALLOWED_HOSTS =
    "portal-api.qa.example.test,portal-health.qa.example.test";
  mismatched.NUZANTARA_API_URL = "https://portal-api.qa.example.test";
  mismatched.MY_PORTAL_BACKEND_HEALTH_URL =
    "https://portal-health.qa.example.test/health";
  assert.match(capturePreflightError(mismatched), /same origin/);
});

test("write policy allows only the explicit frontend and backend origins", () => {
  const allowedOrigins = new Set([
    "http://127.0.0.1:3101",
    "http://127.0.0.1:8000",
  ]);

  assert.equal(
    isUnsafeWriteRequest(
      "POST",
      "http://127.0.0.1:8000/api/auth/login",
      allowedOrigins,
    ),
    false,
  );
  assert.equal(
    isUnsafeWriteRequest(
      "DELETE",
      "http://127.0.0.1:3101/api/auth/logout",
      allowedOrigins,
    ),
    false,
  );
  assert.equal(
    isUnsafeWriteRequest(
      "POST",
      "https://third-party.example.test/collect",
      allowedOrigins,
    ),
    true,
  );
  assert.equal(
    isUnsafeWriteRequest(
      "GET",
      "https://third-party.example.test/static.js",
      allowedOrigins,
    ),
    false,
  );
});

test("network policy rejects every HTTP request outside the QA origins", () => {
  const allowedOrigins = new Set([
    "http://127.0.0.1:3101",
    "http://127.0.0.1:8000",
  ]);

  assert.equal(
    isDisallowedNetworkRequest(
      "http://127.0.0.1:8000/api/portal/dashboard",
      allowedOrigins,
    ),
    false,
  );
  assert.equal(
    isDisallowedNetworkRequest(
      "https://my.balizero.com/portal",
      allowedOrigins,
    ),
    true,
  );
  assert.equal(
    isDisallowedNetworkRequest(
      "https://third-party.example.test/static.js",
      allowedOrigins,
    ),
    true,
  );
  assert.equal(
    isDisallowedNetworkRequest("data:text/plain,synthetic", allowedOrigins),
    false,
  );
});

test("backend health check performs one safe GET and accepts a healthy response", async () => {
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  const fetcher: typeof fetch = async (input, init) => {
    calls.push({ input: String(input), init });
    return new Response(null, { status: 204 });
  };

  await assertBackendHealthy("http://127.0.0.1:8000/health", fetcher);

  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.init?.method, "GET");
  assert.equal(calls[0]?.init?.redirect, "error");
});

test("backend health failures are sanitized", async () => {
  const sensitiveFailure = "synthetic-sensitive-network-detail";
  const fetcher: typeof fetch = async () => {
    throw new Error(sensitiveFailure);
  };

  await assert.rejects(
    assertBackendHealthy("http://127.0.0.1:8000/health", fetcher),
    (error: unknown) => {
      assert.ok(error instanceof ProdlikePreflightError);
      assert.match(error.message, /failed before browser startup/);
      assert.doesNotMatch(error.message, new RegExp(sensitiveFailure));
      return true;
    },
  );
});

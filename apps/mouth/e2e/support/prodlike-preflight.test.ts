import assert from "node:assert/strict";
import test from "node:test";

import {
  assertBackendHealthy,
  assertDocumentSinkHealthy,
  assertMagicLinkSinkHealthy,
  classifyPageError,
  isDisallowedNetworkRequest,
  isUnsafeWriteRequest,
  loadProdlikeEnvironment,
  ProdlikePreflightError,
  REQUIRED_SYNTHETIC_CONTRACTS,
  type EnvironmentSource,
} from "./prodlike-preflight.ts";

const SYNTHETIC_SECRET_SENTINEL = "must-not-appear-in-diagnostics";

function syntheticJwt(payload: Record<string, unknown>): string {
  const encode = (value: unknown): string =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(payload)}.synthetic-signature`;
}

function safeEnvironment(): Record<string, string> {
  const environment = Object.fromEntries(
    REQUIRED_SYNTHETIC_CONTRACTS.map((name) => [name, "synthetic"]),
  );
  environment.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL = "portal-active@example.com";
  environment.MY_PORTAL_SYNTHETIC_CLIENT_PIN = "7412";
  environment.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL =
    "portal-empty@example.com";
  environment.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN = "8523";
  environment.MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_EMAIL =
    "portal-disabled@example.com";
  environment.MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_PIN = "9634";
  environment.MY_PORTAL_SYNTHETIC_PARTNER_EMAIL = "portal-partner@example.com";
  environment.MY_PORTAL_SYNTHETIC_PARTNER_PIN = "1742";
  environment.MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT =
    "portal-support@example.com";
  environment.MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE =
    "synthetic-portal-tenant-boundary.pdf";
  environment.MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID =
    "synthetic_invoice_pdf_fixture_00000001";
  environment.MY_PORTAL_SYNTHETIC_EXPIRED_SESSION = syntheticJwt({
    sub: "00000000-0000-0000-0000-000000000001",
    email: "portal-active@example.com",
    role: "client",
    client_id: 101,
    exp: 1,
  });
  environment.NUZANTARA_API_URL = "http://127.0.0.1:8000";
  environment.MY_PORTAL_BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health";
  environment.PORTAL_BASE_URL = "http://127.0.0.1:3101";
  environment.MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL =
    "http://127.0.0.1:18181/api/notifications/send-email";
  environment.MY_PORTAL_MAGIC_LINK_INBOX_URL =
    "http://127.0.0.1:18181/qa/latest-magic-link";
  environment.MY_PORTAL_MAGIC_LINK_SINK_KEY =
    "synthetic_portal_sink_key_00000001";
  environment.INTERNAL_EMAIL_API_URL =
    environment.MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL;
  environment.NUZANTARA_API_KEY = environment.MY_PORTAL_MAGIC_LINK_SINK_KEY;
  environment.MY_PORTAL_QA_DOCUMENT_SINK_URL = "http://127.0.0.1:18282";
  environment.MY_PORTAL_QA_DOCUMENT_SINK_KEY =
    "synthetic_document_sink_key_00000001";
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
  delete environment.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL;
  delete environment.MY_PORTAL_SYNTHETIC_CLIENT_PIN;

  const message = capturePreflightError(environment);

  assert.match(message, /before browser or network startup/);
  assert.match(message, /MY_PORTAL_SYNTHETIC_CLIENT_EMAIL/);
  assert.match(message, /MY_PORTAL_SYNTHETIC_CLIENT_PIN/);
  assert.doesNotMatch(message, /7412/);
  assert.doesNotMatch(message, /portal-active@example\.com/);
});

test("synthetic fixture values fail closed without being echoed", async (t) => {
  await t.test("reserved domains and distinct accounts", () => {
    const environment = safeEnvironment();
    environment.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL =
      environment.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL;
    const message = capturePreflightError(environment);
    assert.match(message, /portal account emails must be distinct/);
    assert.doesNotMatch(message, /portal-active@example\.com/);

    const sharedSupportRecipient = safeEnvironment();
    sharedSupportRecipient.MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT =
      sharedSupportRecipient.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL;
    const supportMessage = capturePreflightError(sharedSupportRecipient);
    assert.match(
      supportMessage,
      /support and portal account recipients must be distinct/,
    );
    assert.doesNotMatch(supportMessage, /portal-active@example\.com/);
  });

  await t.test("PIN and document contracts", () => {
    const badPin = safeEnvironment();
    badPin.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN = SYNTHETIC_SECRET_SENTINEL;
    const pinMessage = capturePreflightError(badPin);
    assert.match(pinMessage, /MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN/);
    assert.doesNotMatch(pinMessage, new RegExp(SYNTHETIC_SECRET_SENTINEL));

    const badDocument = safeEnvironment();
    badDocument.MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE = "passport.pdf";
    const documentMessage = capturePreflightError(badDocument);
    assert.match(documentMessage, /MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE/);
    assert.doesNotMatch(documentMessage, /passport\.pdf/);

    const badInvoiceFileId = safeEnvironment();
    badInvoiceFileId.MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID =
      SYNTHETIC_SECRET_SENTINEL;
    const invoiceMessage = capturePreflightError(badInvoiceFileId);
    assert.match(invoiceMessage, /MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID/);
    assert.doesNotMatch(invoiceMessage, new RegExp(SYNTHETIC_SECRET_SENTINEL));
  });

  await t.test("expired session shape and expiry", () => {
    const malformed = safeEnvironment();
    malformed.MY_PORTAL_SYNTHETIC_EXPIRED_SESSION = SYNTHETIC_SECRET_SENTINEL;
    const malformedMessage = capturePreflightError(malformed);
    assert.match(malformedMessage, /MY_PORTAL_SYNTHETIC_EXPIRED_SESSION/);
    assert.doesNotMatch(
      malformedMessage,
      new RegExp(SYNTHETIC_SECRET_SENTINEL),
    );

    const unexpired = safeEnvironment();
    unexpired.MY_PORTAL_SYNTHETIC_EXPIRED_SESSION = syntheticJwt({
      sub: "00000000-0000-0000-0000-000000000001",
      email: "portal-active@example.com",
      role: "client",
      client_id: 101,
      exp: Math.floor(Date.now() / 1_000) + 3_600,
    });
    assert.match(
      capturePreflightError(unexpired),
      /MY_PORTAL_SYNTHETIC_EXPIRED_SESSION/,
    );
  });
});

test("page-error diagnostics expose only an allowlisted category", () => {
  const typeError = new TypeError(SYNTHETIC_SECRET_SENTINEL);
  assert.equal(
    classifyPageError(typeError),
    "unhandled page error [TypeError]",
  );

  const customError = new Error(SYNTHETIC_SECRET_SENTINEL);
  customError.name = `Secret-${SYNTHETIC_SECRET_SENTINEL}`;
  const diagnostic = classifyPageError(customError);
  assert.equal(diagnostic, "unhandled page error [OtherError]");
  assert.doesNotMatch(diagnostic, new RegExp(SYNTHETIC_SECRET_SENTINEL));

  const accessControlError = new Error(
    `${SYNTHETIC_SECRET_SENTINEL} due to access control checks.`,
  );
  const accessControlDiagnostic = classifyPageError(accessControlError);
  assert.equal(
    accessControlDiagnostic,
    "unhandled page error [AccessControlError]",
  );
  assert.doesNotMatch(
    accessControlDiagnostic,
    new RegExp(SYNTHETIC_SECRET_SENTINEL),
  );
});

test("the loopback middleware flag cannot be supplied by the caller", () => {
  const environment = safeEnvironment();
  environment.MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE = "1";

  assert.match(
    capturePreflightError(environment),
    /harness injects this loopback-only flag itself/,
  );
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
    assert.equal(environment.emptyClientEmail, "portal-empty@example.com");
    assert.equal(environment.emptyClientPin, "8523");
    assert.equal(
      environment.disabledClientEmail,
      "portal-disabled@example.com",
    );
    assert.equal(environment.disabledClientPin, "9634");
    assert.equal(environment.partnerEmail, "portal-partner@example.com");
    assert.equal(environment.partnerPin, "1742");
    assert.equal(environment.portalBaseUrl, "http://127.0.0.1:3101");
    assert.match(environment.expiredSessionToken, /^[^.]+\.[^.]+\.[^.]+$/);
    assert.equal(
      environment.documentFixtureName,
      "synthetic-portal-tenant-boundary.pdf",
    );
    assert.equal(environment.frontendPort, 3101);
    assert.equal(
      environment.magicLinkSinkHealthUrl,
      "http://127.0.0.1:18181/health",
    );
    assert.equal(
      environment.magicLinkInboxUrl,
      "http://127.0.0.1:18181/qa/latest-magic-link",
    );
    assert.equal(
      environment.documentSinkFailureUrl,
      "http://127.0.0.1:18282/qa/fail-next-upload",
    );
    assert.equal(
      environment.documentSinkHealthUrl,
      "http://127.0.0.1:18282/health",
    );
    assert.equal(
      environment.documentSinkReceiptUrl,
      "http://127.0.0.1:18282/qa/receipt",
    );
    assert.equal(
      environment.supportMailReceiptUrl,
      "http://127.0.0.1:18181/qa/support-mail-receipt",
    );
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

test("the backend magic-link base must match the loopback frontend origin", () => {
  const wrongPort = safeEnvironment();
  wrongPort.PORTAL_BASE_URL = "http://127.0.0.1:3102";
  assert.match(
    capturePreflightError(wrongPort),
    /PORTAL_BASE_URL.*match the loopback frontend origin/,
  );

  const wrongPath = safeEnvironment();
  wrongPath.PORTAL_BASE_URL = "http://127.0.0.1:3101/portal";
  assert.match(
    capturePreflightError(wrongPath),
    /PORTAL_BASE_URL.*match the loopback frontend origin/,
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

test("production domain suffixes cannot be allowlisted", () => {
  for (const hostname of ["portal-api.balizero.com", "preview.fly.dev"]) {
    const environment = safeEnvironment();
    environment.MY_PORTAL_PRODLIKE_ALLOWED_HOSTS = hostname;
    environment.NUZANTARA_API_URL = `https://${hostname}`;
    environment.MY_PORTAL_BACKEND_HEALTH_URL = `https://${hostname}/health`;

    const error = capturePreflightError(environment);
    assert.match(error, /entries must be non-production hostnames/);
    assert.doesNotMatch(error, new RegExp(hostname.replaceAll(".", "\\.")));
  }
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

test("magic-link sink contract is loopback-only and path-bound", () => {
  const external = safeEnvironment();
  external.MY_PORTAL_PRODLIKE_ALLOWED_HOSTS = "mail.qa.example.test";
  external.MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL =
    "https://mail.qa.example.test/api/notifications/send-email";
  external.MY_PORTAL_MAGIC_LINK_INBOX_URL =
    "https://mail.qa.example.test/qa/latest-magic-link";
  assert.match(capturePreflightError(external), /only explicit loopback/);

  const encryptedLoopback = safeEnvironment();
  encryptedLoopback.MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL =
    "https://127.0.0.1:18181/api/notifications/send-email";
  encryptedLoopback.MY_PORTAL_MAGIC_LINK_INBOX_URL =
    "https://127.0.0.1:18181/qa/latest-magic-link";
  encryptedLoopback.INTERNAL_EMAIL_API_URL =
    encryptedLoopback.MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL;
  assert.match(
    capturePreflightError(encryptedLoopback),
    /loopback HTTP endpoints/,
  );

  const wrongPath = safeEnvironment();
  wrongPath.MY_PORTAL_MAGIC_LINK_INBOX_URL =
    "http://127.0.0.1:18181/qa/messages";
  assert.match(
    capturePreflightError(wrongPath),
    /MY_PORTAL_MAGIC_LINK_INBOX_URL.*path is invalid/,
  );

  const weakKey = safeEnvironment();
  weakKey.MY_PORTAL_MAGIC_LINK_SINK_KEY = SYNTHETIC_SECRET_SENTINEL;
  const message = capturePreflightError(weakKey);
  assert.match(message, /MY_PORTAL_MAGIC_LINK_SINK_KEY/);
  assert.doesNotMatch(message, new RegExp(SYNTHETIC_SECRET_SENTINEL));

  const mismatchedBackendEndpoint = safeEnvironment();
  mismatchedBackendEndpoint.INTERNAL_EMAIL_API_URL =
    "http://127.0.0.1:18182/api/notifications/send-email";
  assert.match(
    capturePreflightError(mismatchedBackendEndpoint),
    /INTERNAL_EMAIL_API_URL.*contracts must match/,
  );

  const mismatchedBackendKey = safeEnvironment();
  mismatchedBackendKey.NUZANTARA_API_KEY = "synthetic_portal_sink_key_00000002";
  assert.match(
    capturePreflightError(mismatchedBackendKey),
    /mail sink keys.*must match/,
  );
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

test("magic-link sink health check is GET-only and sanitized", async () => {
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  const healthyFetcher: typeof fetch = async (input, init) => {
    calls.push({ input: String(input), init });
    return new Response(null, { status: 204 });
  };
  await assertMagicLinkSinkHealthy(
    "http://127.0.0.1:18181/health",
    healthyFetcher,
  );
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.init?.method, "GET");

  const sensitiveFailure = "synthetic-sensitive-sink-detail";
  await assert.rejects(
    assertMagicLinkSinkHealthy("http://127.0.0.1:18181/health", async () => {
      throw new Error(sensitiveFailure);
    }),
    (error: unknown) => {
      assert.ok(error instanceof ProdlikePreflightError);
      assert.match(error.message, /sink health check failed/);
      assert.doesNotMatch(error.message, new RegExp(sensitiveFailure));
      return true;
    },
  );
});

test("document sink contract and health check fail closed", async () => {
  const external = safeEnvironment();
  external.MY_PORTAL_QA_DOCUMENT_SINK_URL =
    "https://portal-documents.example.test";
  assert.match(
    capturePreflightError(external),
    /MY_PORTAL_QA_DOCUMENT_SINK_URL.*loopback/,
  );

  const sharedOrigin = safeEnvironment();
  sharedOrigin.MY_PORTAL_QA_DOCUMENT_SINK_URL = "http://127.0.0.1:18181";
  assert.match(
    capturePreflightError(sharedOrigin),
    /document sink.*dedicated loopback origin/,
  );

  const calls: Array<{ input: string; init?: RequestInit }> = [];
  await assertDocumentSinkHealthy(
    "http://127.0.0.1:18282/health",
    async (input, init) => {
      calls.push({ input: String(input), init });
      return new Response(null, { status: 204 });
    },
  );
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.init?.method, "GET");

  const sensitiveFailure = "synthetic-sensitive-document-sink-detail";
  await assert.rejects(
    assertDocumentSinkHealthy("http://127.0.0.1:18282/health", async () => {
      throw new Error(sensitiveFailure);
    }),
    (error: unknown) => {
      assert.ok(error instanceof ProdlikePreflightError);
      assert.match(error.message, /document sink health check failed/);
      assert.doesNotMatch(error.message, new RegExp(sensitiveFailure));
      return true;
    },
  );
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  PROTECTED_API_PATHS,
  PROTECTED_PORTAL_ROUTES,
  PUBLIC_AUTH_ROUTES,
  inspectPublicAuthHtml,
  runPortalPublicLiveGate,
} from "./check-portal-public-live.mjs";

const MY_ORIGIN = "https://my.balizero.com";
const KITA_ORIGIN = "https://kita.balizero.com";
const BACKEND_ORIGIN = "https://nuzantara-rag.fly.dev";
const CSP =
  "default-src 'self'; script-src 'self'; worker-src 'self' blob:; frame-ancestors 'none'; form-action 'self'";

function authHtml() {
  return [
    "<!doctype html><html><head>",
    '<meta name="robots" content="noindex, nofollow">',
    "</head><body>",
    "Public authentication surface",
    "</body></html>",
  ].join("");
}

function response(body, status, headers = {}) {
  return new Response(body, { status, headers });
}

function passingFetch() {
  return async (input, init) => {
    assert.equal(init.method, "GET");
    assert.equal(init.redirect, "manual");
    assert.equal(init.headers.authorization, undefined);
    assert.equal(init.headers.cookie, undefined);

    const url = new URL(input);
    if (url.origin === KITA_ORIGIN && url.pathname === "/") {
      return response(null, 307, { location: "/login" });
    }
    if (
      url.origin === KITA_ORIGIN &&
      url.pathname === "/portal/vault" &&
      url.search === "?folder=annual"
    ) {
      return response(null, 301, {
        location: `${MY_ORIGIN}/portal/vault?folder=annual`,
        "x-robots-tag": "noindex, nofollow",
      });
    }
    if (url.origin === MY_ORIGIN && url.pathname === "/") {
      return response(null, 307, { location: "/portal/login" });
    }
    if (url.origin === MY_ORIGIN && PUBLIC_AUTH_ROUTES.includes(url.pathname)) {
      return response(authHtml(), 200, {
        "content-security-policy": CSP,
        "content-type": "text/html",
      });
    }
    if (
      (url.origin === MY_ORIGIN || url.origin === BACKEND_ORIGIN) &&
      PROTECTED_API_PATHS.includes(url.pathname)
    ) {
      return response(null, 401, { "content-type": "application/json" });
    }
    if (
      url.origin === MY_ORIGIN &&
      (PROTECTED_PORTAL_ROUTES.includes(url.pathname) ||
        (url.pathname === "/portal/vault" && url.search === "?folder=annual"))
    ) {
      const redirect = `${url.pathname}${url.search}`;
      return response(null, 307, {
        location: `/portal/login-upgraded?redirect=${encodeURIComponent(redirect)}`,
      });
    }
    throw new Error(`Unexpected test URL: ${url}`);
  };
}

test("public auth metadata inspection rejects marketing metadata", () => {
  assert.deepEqual(
    inspectPublicAuthHtml(`
      <meta content="noindex, nofollow" name="robots">
      <link href="https://balizero.com" rel="canonical">
      <meta content="Portal" property="og:title">
      <meta name="twitter:card" content="summary">
    `),
    {
      noindex: true,
      nofollow: true,
      hasCanonical: true,
      hasOpenGraph: true,
      hasTwitter: true,
    },
  );
});

test("gate passes the complete read-only public contract", async () => {
  const report = await runPortalPublicLiveGate(passingFetch());

  assert.equal(report.result, "GO");
  assert.deepEqual(report.counts, {
    totalRequests: 39,
    passedRequests: 39,
    failedRequests: 0,
    assertionFailures: 0,
  });
  assert.deepEqual(report.failures, []);
  assert.deepEqual(report.safety.requestMethods, ["GET"]);
  assert.equal(report.safety.credentialsSupplied, false);
  assert.equal(report.safety.responseBodiesRetained, false);
});

test("gate classifies the known stale production contract without raw bodies", async () => {
  const baseFetch = passingFetch();
  const staleFetch = async (input, init) => {
    const url = new URL(input);
    if (
      url.origin === MY_ORIGIN &&
      PROTECTED_PORTAL_ROUTES.includes(url.pathname)
    ) {
      return response("protected shell", 200, {
        "content-security-policy-report-only": CSP,
      });
    }
    if (
      url.origin === MY_ORIGIN &&
      url.pathname === "/portal/forgot-password"
    ) {
      return response("Recover access", 200, {
        "content-security-policy-report-only": CSP,
      });
    }
    return baseFetch(input, init);
  };

  const report = await runPortalPublicLiveGate(staleFetch);

  assert.equal(report.result, "NO_GO");
  assert.ok(report.failures.some(({ id }) => id === "protected:/portal"));
  assert.ok(
    report.failures.some(
      ({ id, observed }) =>
        id === "public-auth:/portal/forgot-password" &&
        observed.includes("metadata fail"),
    ),
  );
  assert.ok(
    report.failures.some(({ id }) => id === "csp:/portal/forgot-password"),
  );
  assert.equal(JSON.stringify(report).includes("protected shell"), false);
  assert.equal(JSON.stringify(report).includes("Recover access"), false);
});

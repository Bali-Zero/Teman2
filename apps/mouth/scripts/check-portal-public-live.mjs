const MY_ORIGIN = "https://my.balizero.com";
const KITA_ORIGIN = "https://kita.balizero.com";
const BACKEND_ORIGIN = "https://nuzantara-rag.fly.dev";

export const PROTECTED_PORTAL_ROUTES = Object.freeze([
  "/portal",
  "/portal/billing",
  "/portal/chat",
  "/portal/companies",
  "/portal/family",
  "/portal/lkpm",
  "/portal/lkpm/submit",
  "/portal/matters",
  "/portal/messages",
  "/portal/partner/commissions",
  "/portal/partner/dashboard",
  "/portal/partner/profile",
  "/portal/partner/referrals",
  "/portal/process",
  "/portal/profile",
  "/portal/settings",
  "/portal/settings/notifications",
  "/portal/taxes",
  "/portal/vault",
  "/portal/visa",
]);

export const PUBLIC_AUTH_ROUTES = Object.freeze([
  "/portal/login-upgraded",
  "/portal/forgot-password",
  "/portal/register",
  "/portal/magic-link",
  "/portal/magic",
]);

export const PROTECTED_API_PATHS = Object.freeze([
  "/api/portal/dashboard",
  "/api/portal/profile",
  "/api/portal/documents",
  "/api/portal/matters",
  "/api/portal/notifications",
]);

const HTML_HEADERS = Object.freeze({
  accept: "text/html,application/xhtml+xml",
  "user-agent": "BaliZeroPortalLiveGate/1.0",
});
const JSON_HEADERS = Object.freeze({
  accept: "application/json",
  "user-agent": "BaliZeroPortalLiveGate/1.0",
});

function addFailure(failures, id, expected, observed) {
  failures.push({ id, expected, observed });
}

function normalizeLocation(location, baseUrl) {
  if (!location) return null;
  try {
    const parsed = new URL(location, baseUrl);
    return `${parsed.origin}${parsed.pathname}${parsed.search}`;
  } catch {
    return "invalid-location";
  }
}

function tagsFor(html, tagName) {
  return html.match(new RegExp(`<${tagName}\\b[^>]*>`, "gi")) ?? [];
}

function attribute(tag, name) {
  const match = tag.match(
    new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, "i"),
  );
  return match?.[1] ?? match?.[2] ?? match?.[3] ?? null;
}

export function inspectPublicAuthHtml(html) {
  const metaTags = tagsFor(html, "meta");
  const linkTags = tagsFor(html, "link");
  const robots = metaTags
    .filter((tag) => attribute(tag, "name")?.toLowerCase() === "robots")
    .map((tag) => attribute(tag, "content")?.toLowerCase() ?? "")
    .join(",");
  const hasCanonical = linkTags.some((tag) =>
    (attribute(tag, "rel") ?? "")
      .toLowerCase()
      .split(/\s+/)
      .includes("canonical"),
  );
  const hasOpenGraph = metaTags.some((tag) =>
    (attribute(tag, "property") ?? "").toLowerCase().startsWith("og:"),
  );
  const hasTwitter = metaTags.some((tag) =>
    (attribute(tag, "name") ?? "").toLowerCase().startsWith("twitter:"),
  );

  return Object.freeze({
    noindex: robots.includes("noindex"),
    nofollow: robots.includes("nofollow"),
    hasCanonical,
    hasOpenGraph,
    hasTwitter,
  });
}

async function request(fetcher, url, headers, readPublicHtml = false) {
  const response = await fetcher(url, {
    method: "GET",
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(15_000),
  });
  let publicHtml = null;
  if (readPublicHtml) {
    publicHtml = await response.text();
  } else {
    await response.body?.cancel();
  }
  return { response, publicHtml };
}

async function checkProductBoundary(fetcher, failures, counters) {
  const cases = [
    {
      id: "kita-root",
      url: `${KITA_ORIGIN}/`,
      status: 307,
      location: `${KITA_ORIGIN}/login`,
    },
    {
      id: "kita-portal-deep-link",
      url: `${KITA_ORIGIN}/portal/vault?folder=annual`,
      status: 301,
      location: `${MY_ORIGIN}/portal/vault?folder=annual`,
      robots: true,
    },
    {
      id: "my-root",
      url: `${MY_ORIGIN}/`,
      status: 307,
      location: `${MY_ORIGIN}/portal/login`,
    },
  ];

  for (const item of cases) {
    counters.total += 1;
    try {
      const { response } = await request(fetcher, item.url, HTML_HEADERS);
      const location = normalizeLocation(
        response.headers.get("location"),
        item.url,
      );
      const robots = response.headers.get("x-robots-tag")?.toLowerCase() ?? "";
      const passed =
        response.status === item.status &&
        location === item.location &&
        (!item.robots ||
          (robots.includes("noindex") && robots.includes("nofollow")));
      if (passed) {
        counters.passed += 1;
      } else {
        addFailure(
          failures,
          item.id,
          `HTTP ${item.status}, location ${item.location}${item.robots ? ", noindex and nofollow" : ""}`,
          `HTTP ${response.status}, location ${location ?? "missing"}${item.robots ? `, robots ${robots || "missing"}` : ""}`,
        );
      }
    } catch (error) {
      addFailure(failures, item.id, "reachable read-only endpoint", error.name);
    }
  }
}

async function checkProtectedPortalRoutes(fetcher, failures, counters) {
  const routes = [
    ...PROTECTED_PORTAL_ROUTES.map((path) => ({ path, redirect: path })),
    {
      path: "/portal/vault?folder=annual",
      redirect: "/portal/vault?folder=annual",
    },
  ];

  for (const item of routes) {
    counters.total += 1;
    const url = `${MY_ORIGIN}${item.path}`;
    const expectedLocation = `${MY_ORIGIN}/portal/login-upgraded?redirect=${encodeURIComponent(item.redirect)}`;
    try {
      const { response } = await request(fetcher, url, HTML_HEADERS);
      const location = normalizeLocation(response.headers.get("location"), url);
      if (response.status === 307 && location === expectedLocation) {
        counters.passed += 1;
      } else {
        addFailure(
          failures,
          `protected:${item.path}`,
          `HTTP 307, location ${expectedLocation}`,
          `HTTP ${response.status}, location ${location ?? "missing"}`,
        );
      }
    } catch (error) {
      addFailure(
        failures,
        `protected:${item.path}`,
        "reachable read-only endpoint",
        error.name,
      );
    }
  }
}

function checkCsp(path, response, failures) {
  const csp =
    response.headers.get("content-security-policy")?.toLowerCase() ?? "";
  const required = [
    "worker-src 'self' blob:",
    "frame-ancestors 'none'",
    "form-action 'self'",
  ];
  const forbidden = ["'unsafe-eval'", "127.0.0.1"];
  if (
    !csp ||
    required.some((directive) => !csp.includes(directive)) ||
    forbidden.some((source) => csp.includes(source))
  ) {
    addFailure(
      failures,
      `csp:${path}`,
      "enforcing portal CSP with worker-src, frame-ancestors, form-action and no unsafe-eval or loopback",
      csp ? "enforcing CSP contract mismatch" : "enforcing CSP missing",
    );
    return false;
  }
  return true;
}

async function checkPublicAuthRoutes(fetcher, failures, counters) {
  for (const path of PUBLIC_AUTH_ROUTES) {
    counters.total += 1;
    const url = `${MY_ORIGIN}${path}`;
    try {
      const { response, publicHtml } = await request(
        fetcher,
        url,
        HTML_HEADERS,
        true,
      );
      const metadata = inspectPublicAuthHtml(publicHtml ?? "");
      const metadataPass =
        metadata.noindex &&
        metadata.nofollow &&
        !metadata.hasCanonical &&
        !metadata.hasOpenGraph &&
        !metadata.hasTwitter;
      const cspPass = checkCsp(path, response, failures);
      if (response.status === 200 && metadataPass && cspPass) {
        counters.passed += 1;
      } else {
        if (response.status !== 200 || !metadataPass) {
          addFailure(
            failures,
            `public-auth:${path}`,
            "HTTP 200, noindex/nofollow, no canonical or social metadata",
            `HTTP ${response.status}, metadata ${metadataPass ? "pass" : "fail"}`,
          );
        }
      }
    } catch (error) {
      addFailure(
        failures,
        `public-auth:${path}`,
        "reachable read-only endpoint",
        error.name,
      );
    }
  }
}

async function checkAnonymousApiAuthorization(fetcher, failures, counters) {
  for (const origin of [MY_ORIGIN, BACKEND_ORIGIN]) {
    for (const path of PROTECTED_API_PATHS) {
      counters.total += 1;
      try {
        const { response } = await request(
          fetcher,
          `${origin}${path}`,
          JSON_HEADERS,
        );
        if (response.status === 401) {
          counters.passed += 1;
        } else {
          addFailure(
            failures,
            `api-auth:${new URL(origin).hostname}${path}`,
            "HTTP 401",
            `HTTP ${response.status}`,
          );
        }
      } catch (error) {
        addFailure(
          failures,
          `api-auth:${new URL(origin).hostname}${path}`,
          "reachable read-only endpoint",
          error.name,
        );
      }
    }
  }
}

export async function runPortalPublicLiveGate(fetcher = globalThis.fetch) {
  const failures = [];
  const counters = { total: 0, passed: 0 };

  await checkProductBoundary(fetcher, failures, counters);
  await checkProtectedPortalRoutes(fetcher, failures, counters);
  await checkPublicAuthRoutes(fetcher, failures, counters);
  await checkAnonymousApiAuthorization(fetcher, failures, counters);

  return Object.freeze({
    schemaVersion: 1,
    result: failures.length === 0 ? "GO" : "NO_GO",
    observedAtUtc: new Date().toISOString(),
    safety: Object.freeze({
      requestMethods: ["GET"],
      credentialsSupplied: false,
      cookiesOrStorageInspected: false,
      responseBodiesRetained: false,
      publicAuthHtmlInspectedTransiently: true,
    }),
    counts: Object.freeze({
      totalRequests: counters.total,
      passedRequests: counters.passed,
      failedRequests: counters.total - counters.passed,
      assertionFailures: failures.length,
    }),
    failures: Object.freeze(failures),
  });
}

async function main() {
  const report = await runPortalPublicLiveGate();
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  process.exitCode = report.result === "GO" ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}

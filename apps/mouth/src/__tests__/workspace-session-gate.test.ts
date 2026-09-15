// APP DOMAIN (kita.balizero.com) had NO server-side session check — the
// workspace auth gate lived entirely in app/(workspace)/layout.tsx, a
// "use client" component, so the SSR HTML payload reached anyone and only
// THEN did browser JS decide to redirect to /login. Measured live
// 2026-09-15T05:17Z against production: every SESSION_GATED_ROUTES entry
// answered anonymous HTTP 200 at 46-77 KB. See the comment above
// SESSION_GATED_ROUTES in ../proxy.ts for the full account.
//
// This file pins the fix: every SESSION_GATED_ROUTES path now redirects an
// anonymous request to /login (GUILT), an authenticated one is untouched
// (INNOCENCE), the two exempted routes (/login, /portal) don't loop or
// double-gate, and every other domain/route class this PR did not intend to
// touch stays exactly as it was.
import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import path from "node:path";
import { fileURLToPath } from "node:url";
import os from "node:os";
import {
  readdirSync,
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  rmSync,
} from "node:fs";
// Next does not export getMiddlewareMatchers's TYPE from its public .d.ts —
// only the compiled JS carries it (verified with `node -e
// "require('next/dist/build/analysis/get-page-static-info').getMiddlewareMatchers"`).
// It is nonetheless the exact function Next's own build step calls to turn
// config.matcher into the ProxyMatcher[]/regex that decides whether a
// request reaches this file at all — which is precisely the mechanism ROUND
// 2 exists to test, so a hand-rolled regex translation here would just be a
// second copy of Next's own compiler, at risk of drifting from it the same
// way the matcher literal drifts from INTERNAL_ROUTES. @ts-expect-error
// (not an `any` cast) so a future next upgrade that starts exporting this
// properly makes this line go red as a prompt to remove the suppression.
// @ts-expect-error — see comment above; no public type for this internal export
import { getMiddlewareMatchers } from "next/dist/build/analysis/get-page-static-info";
import { getMiddlewareRouteMatcher } from "next/dist/shared/lib/router/utils/middleware-route-matcher";
import {
  proxy,
  config,
  isInternalPath,
  INTERNAL_ROUTES,
  SESSION_GATED_ROUTES,
  SESSION_EXEMPT_INTERNAL_ROUTES,
} from "../proxy";
import { walkAppRoutes } from "../../scripts/lib/app-routes.mjs";

const SESSION_COOKIE_HEADER = {
  cookie: "nz_access_token=synthetic-session-token",
};

function createRequest(
  url: string,
  extraHeaders?: Record<string, string>,
): NextRequest {
  const urlObj = new URL(url);
  return new NextRequest(url, {
    headers: {
      host: urlObj.host,
      ...extraHeaders,
    },
  });
}

/** The exact URL the gate redirects to for a given path+search, built the
 * same way the proxy builds it (via URL/searchParams) so percent-encoding
 * can't drift between test and implementation. */
function expectedLoginRedirect(pathAndSearch: string): string {
  const url = new URL("https://kita.balizero.com/login");
  url.searchParams.set("redirect", pathAndSearch);
  return url.toString();
}

// Module-scope so ROUND 2's matcher-invocation-table block AND ROUND 3's
// composite pipeline block share the exact same compiled matcher instead of
// each building its own — "Reuse the existing wouldInvoke setup; do not
// build a second matcher." See the getMiddlewareMatchers import comment
// above for why this is Next's real compiler and not a hand-rolled regex.
const matchers = getMiddlewareMatchers(config.matcher, {});
const wouldInvoke = getMiddlewareRouteMatcher(matchers);
type NoopRequest = Parameters<typeof wouldInvoke>[1];
const noopRequest = { headers: { get: () => null } } as unknown as NoopRequest;

describe("Workspace session gate (kita.balizero.com)", () => {
  describe("GUILT: every SESSION_GATED_ROUTES path is closed to an anonymous request", () => {
    for (const route of SESSION_GATED_ROUTES) {
      it(`redirects anonymous GET ${route} to /login?redirect=${route}`, () => {
        const request = createRequest(`https://kita.balizero.com${route}`);
        const response = proxy(request);

        expect(response.status).toBe(302);
        expect(response.headers.get("location")).toBe(
          expectedLoginRedirect(route),
        );
      });
    }

    it("preserves a deep path AND its query string in the login redirect", () => {
      const request = createRequest(
        "https://kita.balizero.com/clients/123?tab=tax",
      );
      const response = proxy(request);

      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe(
        expectedLoginRedirect("/clients/123?tab=tax"),
      );
    });
  });

  describe("INNOCENCE: an authenticated request is untouched", () => {
    for (const route of SESSION_GATED_ROUTES) {
      it(`allows ${route} through with the session cookie`, () => {
        const request = createRequest(
          `https://kita.balizero.com${route}`,
          SESSION_COOKIE_HEADER,
        );
        const response = proxy(request);

        expect(response.status).not.toBe(301);
        expect(response.status).not.toBe(302);
        expect(response.status).not.toBe(307);
        expect(response.headers.get("x-pathname")).toBe(route);
      });
    }
  });

  describe("INNOCENCE: no login loop on the exempted routes", () => {
    it("does not redirect anonymous /login to itself", () => {
      const request = createRequest("https://kita.balizero.com/login");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(302);
      expect(response.status).not.toBe(307);
    });

    it("does not redirect anonymous /login/anything to /login", () => {
      const request = createRequest("https://kita.balizero.com/login/anything");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(302);
      expect(response.status).not.toBe(307);
    });
  });

  describe("INNOCENCE: app-domain public content still leaves kita anonymously", () => {
    const cases: Array<[string, string]> = [
      ["/team", "https://balizero.com/team"],
      ["/news", "https://balizero.com/news"],
      ["/contact", "https://balizero.com/contact"],
      [
        "/services/visa-assistance",
        "https://balizero.com/services/visa-assistance",
      ],
      // one PUBLIC_CATEGORIES entry
      ["/visas/kitas", "https://balizero.com/visas/kitas"],
    ];

    for (const [from, to] of cases) {
      it(`still 301s ${from} to the public domain with no cookie`, () => {
        const request = createRequest(`https://kita.balizero.com${from}`);
        const response = proxy(request);

        expect(response.status).toBe(301);
        expect(response.headers.get("location")).toBe(to);
      });
    }
  });

  describe("INNOCENCE: public domain (balizero.com) is untouched", () => {
    it("allows / with no cookie", () => {
      const response = proxy(createRequest("https://balizero.com/"));
      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(302);
      expect(response.status).not.toBe(307);
    });

    it.each(["/visas", "/kbli", "/news", "/team", "/contact"])(
      "allows %s with no cookie",
      (route) => {
        const response = proxy(createRequest(`https://balizero.com${route}`));
        expect(response.status).not.toBe(301);
        expect(response.status).not.toBe(302);
        expect(response.status).not.toBe(307);
      },
    );

    it("still 301s /dashboard to the APP domain, not to /login", () => {
      const response = proxy(createRequest("https://balizero.com/dashboard"));
      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/dashboard",
      );
    });
  });

  describe("INNOCENCE: portal domain (my.balizero.com) is untouched by the SESSION_COOKIE rename", () => {
    it("allows a protected portal route with the httpOnly session cookie", () => {
      const request = createRequest(
        "https://my.balizero.com/portal/dashboard",
        SESSION_COOKIE_HEADER,
      );
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/portal/dashboard");
    });

    it("still redirects an anonymous protected portal route to portal login", () => {
      const request = createRequest("https://my.balizero.com/portal/dashboard");
      const response = proxy(request);

      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toBe(
        "https://my.balizero.com/portal/login-upgraded?redirect=%2Fportal%2Fdashboard",
      );
    });
  });
});

// =======================================================================
// Derived class-closer, mirroring internal-routes-cover-workspace.test.ts:
// every first segment of every (workspace) page on disk must be in
// SESSION_GATED_ROUTES, derived from the filesystem rather than trusted by
// name — so a new workspace page nobody gates goes red on the commit that
// adds it, the same way an un-INTERNAL_ROUTES-listed one already does.
// =======================================================================
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.resolve(HERE, "..", "app", "(workspace)");
const MIN_EXPECTED_WORKSPACE_ROUTES = 10;

function workspaceRoutes(): string[] {
  return [
    ...new Set(
      walkAppRoutes(WORKSPACE_DIR)
        .map((p: string) => p.split("/")[0])
        .filter((seg: string) => seg !== "" && !seg.startsWith("[")),
    ),
  ].sort();
}

describe("SESSION_GATED_ROUTES covers every (workspace) page", () => {
  it("has no workspace page that is missing from SESSION_GATED_ROUTES", () => {
    const gated = new Set(SESSION_GATED_ROUTES);
    const uncovered = workspaceRoutes().filter((r) => !gated.has(`/${r}`));
    expect(
      uncovered,
      `these (workspace) pages are not session-gated, so an anonymous request ` +
        `is served the workspace shell with no server-side check: ${uncovered.join(", ")}`,
    ).toEqual([]);
  });

  it("derives the routes rather than trusting a hand-written list (guards the guard)", () => {
    // If the derivation silently returned nothing, the test above would pass
    // while checking nothing at all.
    const routes = workspaceRoutes();
    expect(routes.length).toBeGreaterThan(MIN_EXPECTED_WORKSPACE_ROUTES - 1);
    expect(routes).toContain("lkpm");
    expect(routes).toContain("partners");
  });

  // TRIPWIRE: an exemption must not be able to quietly re-open a workspace
  // page. SESSION_EXEMPT_INTERNAL_ROUTES is only supposed to carve out
  // /login and /portal, neither of which is a (workspace) page — if a future
  // edit ever adds a real workspace route to the exemption set, this fails.
  it("[tripwire] SESSION_EXEMPT_INTERNAL_ROUTES contains no (workspace) page", () => {
    const workspace = new Set(workspaceRoutes().map((r) => `/${r}`));
    const leaked = [...SESSION_EXEMPT_INTERNAL_ROUTES].filter((r) =>
      workspace.has(r),
    );
    expect(
      leaked,
      `these exempted routes are actual (workspace) pages and would be served ` +
        `with no session check: ${leaked.join(", ")}`,
    ).toEqual([]);
  });

  it("SESSION_GATED_ROUTES is INTERNAL_ROUTES minus exactly the exempted routes", () => {
    expect(SESSION_GATED_ROUTES.length).toBe(
      INTERNAL_ROUTES.length - SESSION_EXEMPT_INTERNAL_ROUTES.size,
    );
    for (const route of SESSION_EXEMPT_INTERNAL_ROUTES) {
      expect(SESSION_GATED_ROUTES).not.toContain(route);
    }
  });
});

// =======================================================================
// ROUND 2 — a dot in a dynamic segment value (e.g. /clients/1.2, the
// [id] route with id="1.2") walked past BOTH the gate above AND the
// pre-existing public-domain INTERNAL_ROUTES redirect, because two
// independent mechanisms each treated "pathname contains a dot" as
// synonymous with "is a static asset": config.matcher (Next never invokes
// this file at all for such a path) and the early-return at the top of
// proxy() (this file bails out before reaching any of the logic above).
// Measured live 2026-09-15T05:44Z: balizero.com/clients/1 -> 301 (works),
// balizero.com/clients/1.2 -> 200 at 62,817 bytes (the workspace payload,
// on the public domain, anonymously).
//
// The tests in the two describe blocks above call proxy() DIRECTLY, which
// is exactly why they could not see this: doing so skips config.matcher
// entirely, so all 20 GUILT cases above were proving a function correct
// against paths that, on this exact defect, production never routes to it.
// =======================================================================
describe("ROUND 2: a dotted dynamic-segment value must not bypass either mechanism", () => {
  const COOKIE = { cookie: "nz_access_token=synthetic-session-token" };

  describe("GUILT: the dotted twin of a gated route is closed exactly like the undotted one", () => {
    it("kita.balizero.com/clients/1.2 anonymous -> 302 to /login (was 200)", () => {
      const response = proxy(
        createRequest("https://kita.balizero.com/clients/1.2"),
      );
      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe(
        expectedLoginRedirect("/clients/1.2"),
      );
    });

    it("kita.balizero.com/clients/a.b anonymous -> 302 to /login (arbitrary dotted id, not just numeric)", () => {
      const response = proxy(
        createRequest("https://kita.balizero.com/clients/a.b"),
      );
      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe(
        expectedLoginRedirect("/clients/a.b"),
      );
    });

    it("balizero.com/clients/1.2 anonymous -> 301 to the app domain (was 200, the public-domain half of the same defect)", () => {
      const response = proxy(createRequest("https://balizero.com/clients/1.2"));
      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/clients/1.2",
      );
    });
  });

  describe("INNOCENCE: the dotted twin behaves exactly like the undotted one once it reaches the gate", () => {
    it("kita.balizero.com/clients/1.2 WITH the session cookie is let through", () => {
      const response = proxy(
        createRequest("https://kita.balizero.com/clients/1.2", COOKIE),
      );
      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(302);
      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/clients/1.2");
    });

    it("balizero.com/clients/1.2 WITH the session cookie still 301s to kita (public domain never checks the cookie, same as its undotted twin)", () => {
      const response = proxy(
        createRequest("https://balizero.com/clients/1.2", COOKIE),
      );
      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/clients/1.2",
      );
    });
  });

  describe("INNOCENCE: real static/API paths are untouched by the isInternalPath carve-out", () => {
    it.each([
      "/static/team/adit.jpg",
      "/favicon.ico",
      "/_next/static/x.js",
      "/api/health",
    ])("kita.balizero.com%s is served as-is, no redirect", (route) => {
      const response = proxy(
        createRequest(`https://kita.balizero.com${route}`),
      );
      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(302);
      expect(response.status).not.toBe(307);
    });

    it("isInternalPath rejects a path that merely starts with an internal route's letters (no false prefix match)", () => {
      // /administration is not "/admin" plus a segment boundary — it must
      // not be swept into the internal-route carve-out by a bare
      // startsWith("/admin") without the trailing "/".
      expect(isInternalPath("/administration")).toBe(false);
      expect(isInternalPath("/admin")).toBe(true);
      expect(isInternalPath("/admin/users")).toBe(true);
    });
  });
});

// =======================================================================
// ROUND 2 — the drift killer. config.matcher's second entry is a
// hand-written literal (Next requires the matcher to be statically
// analysable, so it cannot be computed from INTERNAL_ROUTES at build time),
// which means it is exactly the shape of coupling this repo's scar record
// warns about: a second copy of a list that only stays correct if someone
// remembers to update it by hand. This test parses the alternation back out
// of the live config.matcher string and compares it against INTERNAL_ROUTES
// itself, in both directions, so adding a route to one without the other is
// red on the commit that does it — not discovered later, live, by an
// external probe.
// =======================================================================
/** Extracts the `/(a|b|c)/:path*`-shaped second matcher entry's route list. */
function extractAlternationRoutes(matcherEntries: string[]): string[] {
  for (const entry of matcherEntries) {
    const match = entry.match(/^\/\(([^)]+)\)\/:path\*$/);
    if (match) {
      return match[1].split("|").map((segment) => `/${segment}`);
    }
  }
  return [];
}

/** The comparison itself — exercised once for real, once as a guilt control. */
function diffMatcherRoutes(matcherRoutes: string[], internalRoutes: string[]) {
  const matcherSet = new Set(matcherRoutes);
  const internalSet = new Set(internalRoutes);
  return {
    missingFromMatcher: internalRoutes.filter((r) => !matcherSet.has(r)),
    extraInMatcher: matcherRoutes.filter((r) => !internalSet.has(r)),
  };
}

describe("config.matcher's second entry tracks INTERNAL_ROUTES exactly (no drift, either direction)", () => {
  it("has every INTERNAL_ROUTES entry in the matcher, and nothing in the matcher that isn't in INTERNAL_ROUTES", () => {
    const matcherRoutes = extractAlternationRoutes(config.matcher);
    // Guards the guard: if the regex above stopped matching config.matcher's
    // actual shape (e.g. someone reformatted the literal), this would
    // silently return [] and the comparison below would pass on an empty set.
    expect(matcherRoutes.length).toBeGreaterThan(0);

    const diff = diffMatcherRoutes(matcherRoutes, INTERNAL_ROUTES);
    expect(
      diff.missingFromMatcher,
      `these INTERNAL_ROUTES entries are missing from config.matcher, so a ` +
        `dotted value in their dynamic segment still bypasses this file entirely: ` +
        diff.missingFromMatcher.join(", "),
    ).toEqual([]);
    expect(
      diff.extraInMatcher,
      `these config.matcher entries have no INTERNAL_ROUTES twin — dead weight ` +
        `at best, a route this file was never meant to widen at worst: ` +
        diff.extraInMatcher.join(", "),
    ).toEqual([]);
  });

  it("[guilt control] the same comparison DOES reject a deliberately mismatched pair", () => {
    // A fabricated matcher list: missing most of INTERNAL_ROUTES, and
    // carrying one route INTERNAL_ROUTES doesn't have. If this test can't
    // fail, the real test above is vacuous.
    const mismatched = ["/accounting", "/admin", "/not-a-real-internal-route"];
    const diff = diffMatcherRoutes(mismatched, INTERNAL_ROUTES);
    expect(diff.missingFromMatcher.length).toBeGreaterThan(0);
    expect(diff.extraInMatcher).toEqual(["/not-a-real-internal-route"]);
  });
});

// =======================================================================
// ROUND 2 — exercising the MATCHER, not the function. Every test above
// (this file and middleware.test.ts) calls proxy() directly, which — as
// this whole round exists to prove — is not the same question as "does
// Next invoke proxy() for this path at all". This block uses Next's own
// matcher compiler (the same one `next build` runs on config.matcher) so
// the answer isn't a hand-rolled regex translation that could itself drift
// from what Next actually does.
// =======================================================================
describe("config.matcher — which paths actually reach proxy() in production", () => {
  const cases: Array<[path: string, invoked: boolean, reason: string]> = [
    ["/clients/1", true, "internal route, no dot"],
    [
      "/clients/1.2",
      true,
      "THE BUG this round fixes: a dotted [id] value under an internal route",
    ],
    ["/clients/a.b", true, "same class, a non-numeric dotted id"],
    [
      "/lkpm.json",
      true,
      "not a real route (no page answers it — verified: it falls through to " +
        "the (blog)/[category] catch-all) — invoked because Next's matcher " +
        "compiler auto-appends an optional .json/.rsc DATA-ROUTE transport " +
        "suffix to every entry, matching 'lkpm' + '.json'; proxy()'s own " +
        "isInternalPath still rejects it (no '/' boundary), so this is not " +
        "a new gate — same 200 as before, just routed through this file now",
    ],
    ["/dashboard", true, "internal route, no dot, unaffected by this round"],
    ["/static/team/x.jpg", false, "excluded — static asset"],
    ["/_next/static/chunk.js", false, "excluded — Next internal asset"],
    ["/api/health", false, "excluded — API route"],
    ["/favicon.ico", false, "excluded — favicon"],
    ["/news/some-article", true, "public content route, no dot, unaffected"],
    ["/kbli/12345", true, "public content route, no dot, unaffected"],
  ];

  it.each(cases)("%s -> invoked=%s (%s)", (path, invoked) => {
    expect(wouldInvoke(path, noopRequest, {})).toBe(invoked);
  });

  it("/static/... and /_next/... and /api/... are never invoked, no matter which matcher entry is checked", () => {
    for (const path of [
      "/static/team/x.jpg",
      "/_next/static/chunk.js",
      "/api/health",
    ]) {
      expect(wouldInvoke(path, noopRequest, {})).toBe(false);
    }
  });

  it("every INTERNAL_ROUTES entry, dotted or not, is invoked", () => {
    for (const route of INTERNAL_ROUTES) {
      expect(wouldInvoke(route, noopRequest, {})).toBe(true);
      expect(wouldInvoke(`${route}/1.2`, noopRequest, {})).toBe(true);
    }
  });
});

// =======================================================================
// ROUND 3 (Gemini review, disposed CURE 1) — round 1 missed the dot bypass
// precisely because wouldInvoke (the real Next matcher, above) and proxy()
// were asserted in SEPARATE describe blocks: each could pass on its own
// narrower assumptions while the COMBINED production pipeline — matcher
// decides whether Next calls proxy() at all, THEN proxy() decides what to
// do — failed end to end for a dotted dynamic-segment value. This block
// asserts both halves in one step, per path, so that class of gap can't
// reopen the same way.
// =======================================================================
describe("ROUND 3: composite pipeline — the real matcher AND proxy() asserted together, not in separate blocks", () => {
  /** Both halves in one step: the real Next matcher says proxy() is actually
   * invoked for this path, AND proxy() itself sends an anonymous request to
   * the gate's /login. Either half passing alone proves nothing about
   * production, which routes through both in sequence. */
  function expectGatedThroughRealPipeline(pathname: string) {
    expect(
      wouldInvoke(pathname, noopRequest, {}),
      `Next's real matcher must invoke proxy() for ${pathname}, or the session gate below never runs in production`,
    ).toBe(true);

    const response = proxy(
      createRequest(`https://kita.balizero.com${pathname}`),
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe(
      expectedLoginRedirect(pathname),
    );
  }

  /** Inverse: whatever the real matcher decides for this public path,
   * proxy() itself must never answer it with a 302 to /login. */
  function expectNeverGatedToLogin(pathname: string, hostname: string) {
    const invoked = wouldInvoke(pathname, noopRequest, {});
    const response = proxy(createRequest(`https://${hostname}${pathname}`));
    const location = response.headers.get("location");
    const gatedToLogin =
      response.status === 302 && !!location?.includes("/login");
    expect(
      gatedToLogin,
      `${hostname}${pathname} (matcher invoked=${invoked}) must not be sent to /login`,
    ).toBe(false);
  }

  it.each([
    "/clients/1",
    "/clients/1.2",
    "/clients/a.b/c",
    "/lkpm",
    "/dashboard",
    "/settings/profile.v2",
  ])(
    "%s: the real matcher invokes proxy(), AND proxy() gates it to /login",
    (pathname) => {
      expectGatedThroughRealPipeline(pathname);
    },
  );

  it.each([
    ["/", "balizero.com"],
    ["/visas", "balizero.com"],
    ["/news/some-article", "balizero.com"],
    ["/static/team/adit.jpg", "kita.balizero.com"],
  ] as Array<[string, string]>)(
    "%s on %s: proxy() never gates it to /login, regardless of matcher invocation",
    (pathname, hostname) => {
      expectNeverGatedToLogin(pathname, hostname);
    },
  );
});

// =======================================================================
// ROUND 3 (Gemini review, disposed CURE 2) — an empty or whitespace-only
// session cookie must not be treated as a valid session. The point is
// forward-looking: a future refactor from `.get()?.value` truthiness to
// `.has()` presence would silently accept a present-but-empty cookie as a
// session (a real cookie-clearing idiom is `Set-Cookie: name=; Max-Age=0`,
// which leaves the name present with an empty value on the NEXT request in
// some client/proxy combinations). See §ROUND 3 mutation proof in
// REPORT-RA.md for the mutation that verifies this test is load-bearing.
// =======================================================================
describe("ROUND 3: an empty or whitespace-only session cookie is not a session", () => {
  it("cookie: nz_access_token= (empty value) is NOT a session -> 302 to /login", () => {
    const response = proxy(
      createRequest("https://kita.balizero.com/dashboard", {
        cookie: "nz_access_token=",
      }),
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe(
      expectedLoginRedirect("/dashboard"),
    );
  });

  it("cookie: nz_access_token=   (whitespace-only value) is NOT a session -> 302 to /login", () => {
    const response = proxy(
      createRequest("https://kita.balizero.com/dashboard", {
        cookie: "nz_access_token=   ",
      }),
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe(
      expectedLoginRedirect("/dashboard"),
    );
  });
});

// =======================================================================
// ROUND 4 (red-team found, Dux confirmed live 2026-09-15T06:40Z) — rounds
// 1-3 gated the ACTION (`return response` handing a request to rendering)
// at exactly one call-site, the APP DOMAIN block. Three more call-sites
// return `response` the same way, on hosts the spec never enumerated:
//   zantara.balizero.com/lkpm      -> 200, 49,024 B, 2 excluded-roster markers (== kita)
//   zantara.balizero.com/clients/1 -> 200, 62,811 B
//   zantara.balizero.com/dashboard -> 200
// Fixed in proxy.ts by extracting the gate into sessionGateRedirect() and
// calling it before every one of those returns (ZANTARA DOMAIN, the isFlyDev
// bypass, the final fall-through for an unclassified hostname). This block
// is the class-closer: a HOST x PATH table, so a future host branch that
// forgets to call the gate is one row to add here, not a live discovery.
// =======================================================================
const HOST_MATRIX_HOSTS = [
  "kita.balizero.com",
  "zantara.balizero.com",
  "some-app.fly.dev",
  "preview.unclassified-host.example",
];
const HOST_MATRIX_PATHS = ["/lkpm", "/clients/1", "/clients/1.2", "/dashboard"];

describe("ROUND 4: host matrix — the gate fires on every host that can reach rendering, not just kita", () => {
  for (const host of HOST_MATRIX_HOSTS) {
    for (const gatedPath of HOST_MATRIX_PATHS) {
      it(`${host}${gatedPath} anonymous -> 302, Location path /login, redirect=${gatedPath}`, () => {
        const response = proxy(createRequest(`https://${host}${gatedPath}`));
        expect(response.status).toBe(302);

        // Same-origin by construction (new URL("/login", request.url)), so
        // the host varies with the request — only the PATH and the redirect
        // PARAM are the contract this table is pinning.
        const location = new URL(response.headers.get("location") as string);
        expect(location.pathname).toBe("/login");
        expect(location.searchParams.get("redirect")).toBe(gatedPath);
      });

      it(`${host}${gatedPath} WITH session cookie -> not a redirect, carries x-pathname`, () => {
        const response = proxy(
          createRequest(`https://${host}${gatedPath}`, SESSION_COOKIE_HEADER),
        );
        expect(response.status).not.toBe(301);
        expect(response.status).not.toBe(302);
        expect(response.status).not.toBe(307);
        expect(response.headers.get("x-pathname")).toBe(gatedPath);
      });
    }
  }
});

describe("ROUND 4: pinned exclusions — the widened gate must not touch these", () => {
  it("balizero.com/lkpm anonymous still 301s to kita, not to /login (public-domain redirect unaffected)", () => {
    const response = proxy(createRequest("https://balizero.com/lkpm"));
    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toBe(
      "https://kita.balizero.com/lkpm",
    );
  });

  it("localhost:3000/lkpm still passes through with no gate (dev bypass intact)", () => {
    const response = proxy(createRequest("http://localhost:3000/lkpm"));
    expect(response.status).not.toBe(301);
    expect(response.status).not.toBe(302);
    expect(response.status).not.toBe(307);
  });

  it("zantara.balizero.com/ still rewrites to /chat, not gated", () => {
    const response = proxy(createRequest("https://zantara.balizero.com/"));
    expect(response.status).not.toBe(302);
    expect(response.headers.get("x-pathname")).toBe("/");
  });
});

// =======================================================================
// ROUND 4 (Codex HIGH #4) — the derived class-closer above
// (`SESSION_GATED_ROUTES covers every (workspace) page`) filters OUT any
// top-level segment starting with "[" before comparing against
// SESSION_GATED_ROUTES. That is correct for what it checks today (no such
// route exists), but it means a future `(workspace)/[tenant]/page.tsx`
// would be silently invisible to that test — a real workspace route added
// with every test staying green. A dynamic top-level segment cannot be
// expressed as an INTERNAL_ROUTES literal prefix anyway (INTERNAL_ROUTES
// requires an exact string), so it can never be auto-covered — it needs an
// explicit gating decision (e.g. exact-path handling in sessionGateRedirect
// itself) at the point it's added, not silent omission from this check.
// =======================================================================
function topLevelDynamicSegments(routes: string[]): string[] {
  return [
    ...new Set(
      routes.map((p) => p.split("/")[0]).filter((seg) => seg.startsWith("[")),
    ),
  ].sort();
}

describe("ROUND 4: a top-level dynamic (workspace) route is never silently ungated", () => {
  it("[guilt control] topLevelDynamicSegments catches a [tenant]/page.tsx fixture — proves the check is not vacuous", () => {
    // A real temp dir (not the repo tree), so this is not a hand-rolled
    // reimplementation of the filter — it runs the SAME walkAppRoutes this
    // suite uses against WORKSPACE_DIR, just pointed at a fixture.
    const tmpDir = mkdtempSync(
      path.join(os.tmpdir(), "workspace-gate-dynamic-route-"),
    );
    try {
      const tenantDir = path.join(tmpDir, "[tenant]");
      mkdirSync(tenantDir, { recursive: true });
      writeFileSync(
        path.join(tenantDir, "page.tsx"),
        "export default function Page() { return null; }\n",
      );

      const routes = walkAppRoutes(tmpDir);
      const dynamic = topLevelDynamicSegments(routes);

      // RED-THEN-GREEN, recorded in REPORT-RA.md ROUND 4: asserting
      // `toEqual([])` here (the same shape as the real tripwire below) goes
      // red against this exact fixture, because the fixture is deliberately
      // uncovered by construction — proving the assertion shape can fail.
      // Restoring the correct expectation below goes green again.
      expect(dynamic).toEqual(["[tenant]"]);
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("[tripwire] the real (workspace) tree has no top-level dynamic route today — passes now, and must stay an explicit decision if one is ever added", () => {
    const dynamic = topLevelDynamicSegments(walkAppRoutes(WORKSPACE_DIR));
    expect(
      dynamic,
      `these top-level (workspace) routes are dynamic segments and cannot be ` +
        `expressed as an INTERNAL_ROUTES literal prefix — each needs an explicit ` +
        `gating decision before merging, not silent omission from the coverage ` +
        `check: ${dynamic.join(", ")}`,
    ).toEqual([]);
  });
});

// =======================================================================
// ROUND 4 (Codex LOW #6) — round 2 widened config.matcher's second entry to
// invoke proxy() for a DOTTED path under an internal prefix (see
// isInternalPath's comment). The flip side: it now also invokes proxy() for
// an UNDOTTED real static file under one of those prefixes — which would
// hit sessionGateRedirect and get redirected to /login instead of served.
// The Dux verified none exists today; this pins that fact so it stays true.
// =======================================================================
const PUBLIC_DIR = path.resolve(HERE, "..", "..", "public");

/** Every immediate child name of `dir` — the "first segment" any request
 * path under it would carry. */
function topLevelEntries(dir: string): string[] {
  return readdirSync(dir).sort();
}

function findInternalRouteCollisions(segments: string[]): string[] {
  const internalLower = new Set(
    INTERNAL_ROUTES.map((route) => route.slice(1).toLowerCase()),
  );
  return segments.filter((segment) => internalLower.has(segment.toLowerCase()));
}

describe("ROUND 4: no real file under public/ collides with an INTERNAL_ROUTES prefix", () => {
  it("[guards the guard] the public/ walk is not silently empty", () => {
    expect(topLevelEntries(PUBLIC_DIR).length).toBeGreaterThan(0);
  });

  it("[guilt control] the collision check DOES reject a deliberately colliding synthetic list", () => {
    const collisions = findInternalRouteCollisions([
      "assets",
      "ADMIN",
      "images",
    ]);
    // Case-insensitive: "ADMIN" must still collide with "/admin".
    expect(collisions).toEqual(["ADMIN"]);
  });

  it("has no public/ top-level entry matching an INTERNAL_ROUTES prefix, case-insensitive", () => {
    const collisions = findInternalRouteCollisions(topLevelEntries(PUBLIC_DIR));
    expect(
      collisions,
      `these public/ top-level entries collide with an INTERNAL_ROUTES prefix; the ` +
        `matcher round 2 widened now invokes proxy() for a real file under them, and ` +
        `an authenticated OR anonymous request for it would hit the session gate ` +
        `instead of being served: ${collisions.join(", ")}`,
    ).toEqual([]);
  });
});

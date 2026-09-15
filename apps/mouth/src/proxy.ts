import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { normalizeHostname } from "@/lib/hostname";

/**
 * Multi-domain Middleware
 *
 * Handles routing between:
 * - balizero.com (public website)
 * - kita.balizero.com (internal app)
 */

// Internal app routes that should only be on zantara subdomain.
//
// EXPORTED so the test that proves every (workspace) page is covered can read the
// real array instead of parsing this file with a regex. The parsing version worked
// until it didn't: it matched only double quotes, it would have swallowed any quoted
// token inside a comment, and a type annotation on this line would have broken it
// outright — a test whose weaker half was a hand-maintained coupling to source text.
//
// WARNING: config.matcher at the bottom of this file carries a LITERAL COPY of
// these route prefixes, hand-alternated — Next requires config.matcher to be
// statically analysable, so it cannot be computed from this array at build
// time. Add a route here without also adding it to that matcher literal and
// any dotted path under it (e.g. /new-route/1.2, a dynamic segment value that
// happens to contain a dot) is left ungated: Next never invokes proxy() for
// it at all, so the session gate below never even runs. The parity test in
// src/__tests__/workspace-session-gate.test.ts ("config.matcher's second
// entry tracks INTERNAL_ROUTES exactly") is what turns that omission red.
export const INTERNAL_ROUTES = [
  "/login",
  "/dashboard",
  "/clients",
  "/process",
  "/second-home",
  "/settings",
  "/lkpm", // workspace LKPM batch — answered 200 on the public domain until 2026-09-12
  "/admin",
  "/agents",
  "/portal",
  "/analytics",
  "/intelligence",
  "/notifications",
  // The eight below were workspace pages that answered 200 on the PUBLIC domain —
  // the same hole /lkpm had, eight times over, and present since long before it was
  // found. Each was verified before being listed: the public body is BYTE-IDENTICAL
  // to the one kita serves, HTTP 200, and carries 0 staff markers, so each is the
  // workspace shell and not a public page someone meant to publish.
  // Measured 2026-09-13 against the deployment then serving:
  //   accounting 49,666 B · garuda-voa 49,185 · hr 46,166 · obligations 45,414
  //   omnichannel 45,922 · partners 45,951 · review 45,396 · terminal 46,299
  "/accounting",
  "/garuda-voa",
  "/hr",
  "/obligations",
  "/omnichannel",
  "/partners",
  "/review",
  "/terminal",
];

// Exact-segment match over the FULL route list (unlike SESSION_GATED_ROUTES,
// this one still includes /login and /portal). Used in TWO places below: the
// early-return's dotted-path exclusion, and the public-domain 301.
//
// Measured live 2026-09-15T05:44Z against production: balizero.com/clients/1
// 301s to kita as expected, but balizero.com/clients/1.2 answered anonymous
// HTTP 200 at 62,817 bytes — the workspace payload, on the PUBLIC domain, for
// a dynamic route segment ([id]) that happens to contain a dot. Two causes
// stack: (1) config.matcher below excludes every path containing a dot, so
// Next never even invokes this function for it; (2) the early-return a few
// lines down independently skips any dotted path too. A dotted id walks past
// both the session gate AND the public-domain redirect the five PRs before
// this one (#6327 #6361 #6391 #6397 #6400) built — because both mechanisms
// treated "has a dot" as synonymous with "is a static asset", which is false
// for `/clients/[id]` and every other dynamic segment under INTERNAL_ROUTES.
export function isInternalPath(pathname: string): boolean {
  return INTERNAL_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

// APP DOMAIN had NO server-side session check at all. The workspace auth gate
// lived entirely in app/(workspace)/layout.tsx, a "use client" component — so
// the SSR HTML payload was sent to ANYONE, and only THEN did browser JS decide
// whether to redirect to /login. A client component can style the wait for a
// redirect; it cannot BE the gate, because by the time it runs the bytes it
// would have hidden already left the server.
//
// Measured live 2026-09-15T05:17Z against production, anonymously, all HTTP
// 200 at 46-77 KB each: /lkpm /dashboard /clients /accounting /garuda-voa /hr
// /intelligence /notifications /obligations /omnichannel /partners /process
// /review /second-home /settings /terminal /admin /analytics /agents. /lkpm's
// anonymous payload carried 2 excluded-roster markers.
//
// SESSION_EXEMPT_INTERNAL_ROUTES carves the two INTERNAL_ROUTES entries that
// must stay reachable with NO session: /login is the login page itself
// (gating it is an infinite redirect loop back to itself), and /portal is
// already redirected off to my.balizero.com earlier in this file and gated
// there via SESSION_COOKIE / hasSession() — gating it again here would be a
// second, redundant mechanism guarding a route this file never actually
// serves.
export const SESSION_EXEMPT_INTERNAL_ROUTES = new Set<string>([
  "/login",
  "/portal",
]);

// EXPORTED for the same reason INTERNAL_ROUTES is: a test can import the real
// derived array instead of recomputing the filter against source text.
export const SESSION_GATED_ROUTES = INTERNAL_ROUTES.filter(
  (route) => !SESSION_EXEMPT_INTERNAL_ROUTES.has(route),
);

function isSessionGatedPath(pathname: string): boolean {
  return SESSION_GATED_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

// /knowledge is NOT a route on kita — it maps 1:1 to a standalone app on its
// own subdomain. See APP_SUBDOMAIN_ROUTE_MAP in the APP DOMAIN block.
const APP_SUBDOMAIN_ROUTE_MAP: Record<string, string> = {
  "/knowledge": "knowledge.balizero.com",
};

// /email leaves the fleet: mail.balizero.com is gone, and Bali Zero mail lives
// in Zoho. An existing Zoho session lands straight in the inbox; without one,
// Zoho bounces through its own login and comes back here.
const ZOHO_MAILBOX_URL = "https://mail.zoho.com/zm/";

// Retired: the standalone calendar/drive apps were deleted in 7f287c623
// (2026-04-17) and their DNS now answers 404 DEPLOYMENT_NOT_FOUND, so these
// paths must not be redirected off-site any more.
const RETIRED_APP_ROUTES = ["/calendar", "/documents"];

// Public routes for balizero.com
const PUBLIC_CATEGORIES = [
  "immigration",
  "visas",
  "business",
  "tax-legal",
  "taxes",
  "property",
  "lifestyle",
  "living",
  "digital-nomad",
  "tech",
  "trends",
];

// Domains
const PUBLIC_DOMAIN = "balizero.com";
const APP_DOMAIN = "kita.balizero.com";
const PORTAL_DOMAIN = "my.balizero.com";
const MOBILE_DOMAIN = "mo.balizero.com";
const ZANTARA_DOMAIN = "zantara.balizero.com";
const VISA_DOMAIN = "visa.balizero.com";
const TAX_DOMAIN = "tax.balizero.com";
const NUZANTARA_DOMAIN = "nuzantara.co.id";
const ASSESSMENT_DOMAIN = "subhi.balizero.com";
// SSO subdomains: standalone apps on *.balizero.com that share auth via cookie.
// mouth does not serve these hostnames directly (each is its own Vercel deploy
// that redirects unauthenticated visitors to kita.balizero.com/login?redirect=...),
// but they must stay classified as isAppDomain (not isPublicDomain) so a request
// that somehow reaches this middleware for one of them doesn't get treated as
// public marketing content.
const SSO_SUBDOMAINS = ["mail", "calendar", "drive", "knowledge"];
// Deliberately shared across *.balizero.com (Domain=.balizero.com in
// production), set by app/api/auth/login/route.ts so every subdomain sees
// the same session. This file checks PRESENCE only (see hasSession below) —
// role and token validity are enforced downstream by the backend on every
// data request, so a forged or stale cookie value gets at most an empty
// workspace shell here, never actual client data.
const SESSION_COOKIE = "nz_access_token";
const PORTAL_PUBLIC_PATHS = new Set([
  "/portal/login",
  "/portal/login-upgraded",
  "/portal/forgot-password",
  "/portal/register",
  "/portal/magic-link",
  "/portal/magic",
]);

// Scraper detection — classify requests as human, welcome bot, or suspicious
const WELCOME_BOTS =
  /Googlebot|Bingbot|GPTBot|ClaudeBot|anthropic|PerplexityBot|Applebot|DuckDuckBot|Bytespider|Amazonbot|YouBot|FacebookBot|CCBot/i;
const SCRAPER_SIGNATURES =
  /python-requests|scrapy|curl\/|wget\/|Go-http-client|node-fetch|axios\/\d|PhantomJS|HeadlessChrome|Selenium|Nightmare|puppeteer/i;

/**
 * Detect RSC/prefetch requests that should NOT be cross-origin redirected.
 * Next.js Link prefetches trigger RSC fetches; redirecting these cross-origin
 * causes CORS errors that flood the console and slow down the page.
 *
 * The `_rsc` query param and `RSC`/`Next-Router-Prefetch` headers are stripped
 * by Next.js before requests reach middleware in production builds, so none of
 * them ever match live. The one signal that survives is the `Accept` header:
 * Next.js's RSC fetch client always sends `Accept: text/x-component`, while a
 * real browser navigation sends `Accept: text/html`. Match on that.
 */
function isRSCOrPrefetch(request: NextRequest): boolean {
  return (
    request.nextUrl.searchParams.has("_rsc") ||
    request.headers.get("RSC") === "1" ||
    request.headers.get("Next-Router-Prefetch") === "1" ||
    request.headers.get("Purpose") === "prefetch" ||
    (request.headers.get("accept") || "").includes("text/x-component")
  );
}

/**
 * Redirect to a cross-origin URL, but return 204 for RSC/prefetch requests
 * to prevent CORS errors in the browser console.
 */
function crossOriginRedirect(
  request: NextRequest,
  targetUrl: URL,
  status: 301 | 302 = 301,
): NextResponse {
  if (isRSCOrPrefetch(request)) {
    return new NextResponse(null, { status: 204 });
  }
  const redirectResponse = NextResponse.redirect(targetUrl, status);
  redirectResponse.headers.set("x-pathname", request.nextUrl.pathname);
  return redirectResponse;
}

function classifyRequest(
  request: NextRequest,
): "human" | "welcome-bot" | "suspicious" {
  const ua = request.headers.get("user-agent") || "";
  const accept = request.headers.get("accept") || "";

  if (WELCOME_BOTS.test(ua)) return "welcome-bot";
  if (!ua || !accept) return "suspicious";
  if (SCRAPER_SIGNATURES.test(ua)) return "suspicious";

  return "human";
}

function matchesDomain(
  hostname: string,
  domain: string,
  allowWWW = true,
): boolean {
  return hostname === domain || (allowWWW && hostname === `www.${domain}`);
}

function isPortalPath(pathname: string): boolean {
  return pathname === "/portal" || pathname.startsWith("/portal/");
}

function hasSession(request: NextRequest): boolean {
  return Boolean(request.cookies.get(SESSION_COOKIE)?.value);
}

// The gate is a property of the PATH, not of the host: a SESSION_GATED_ROUTES
// path must never reach page rendering for an anonymous caller, at EVERY
// point in this file that hands a request to rendering — not only the one
// branch (APP DOMAIN) round 1 gated. Live measurement, 2026-09-15T06:40Z,
// production, anonymous, red-team-found and Dux-confirmed:
//   zantara.balizero.com/lkpm       -> 200, 49,024 B, 2 excluded-roster markers (== kita's /lkpm)
//   zantara.balizero.com/clients/1  -> 200, 62,811 B
//   zantara.balizero.com/dashboard  -> 200
// Root cause: the ZANTARA DOMAIN block's non-root branch does `return
// response` before control ever reaches the APP DOMAIN block's gate — same
// app, same pages, different host. Two more `return response;`s share the
// exact shape and now also call this helper first: the isFlyDev bypass (any
// public *.fly.dev host, not a development machine) and the final
// fall-through for any hostname no branch above classifies.
//
// NOT gated here, and why each is safe:
// - PUBLIC domain (balizero.com): isInternalPath() already 301s every
//   SESSION_GATED_ROUTES path to kita before that block's own `return
//   response`, so that fall-through never carries a gated path.
// - PORTAL domain (my.balizero.com): has its own session check
//   (hasSession()/PORTAL_PUBLIC_PATHS) and redirects every non-/portal path
//   off-host — it never itself renders a workspace page.
// - MOBILE/www/VISA/TAX/NUZANTARA/ASSESSMENT blocks (mo., www., visa., tax.,
//   nuzantara.co.id, subhi.): each unconditionally redirects or rewrites
//   EVERY path into its own namespace (/visa, /tax-calendar/*, /nuzantara/*,
//   /assessment/*) or off-host; none of those namespaces overlaps
//   SESSION_GATED_ROUTES, so none of them can land on a workspace page.
function sessionGateRedirect(
  request: NextRequest,
  pathname: string,
): NextResponse | null {
  if (!isSessionGatedPath(pathname) || hasSession(request)) {
    return null;
  }
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("redirect", `${pathname}${request.nextUrl.search}`);
  // Same-origin (relative to request.url): no CORS reason to route this
  // through crossOriginRedirect, and doing so would be actively wrong — it
  // returns 204 for RSC/prefetch, which would answer an RSC fetch of a gated
  // workspace route with an empty 204 instead of sending it to /login.
  const gateResponse = NextResponse.redirect(loginUrl, 302);
  gateResponse.headers.set("x-pathname", pathname);
  // A fresh NextResponse does not inherit X-Robots-Tag from the caller's
  // `response` — set it explicitly, same reason every other redirect in this
  // file that replaces `response` re-sets it.
  gateResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
  return gateResponse;
}

export function proxy(request: NextRequest) {
  const hostname = normalizeHostname(request.headers.get("host") || "");
  const pathname = request.nextUrl.pathname;

  // Skip static files and API routes
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/static") ||
    // Files with extensions — EXCEPT an internal path, because a dynamic
    // segment value can legitimately contain a dot (/clients/1.2 is the
    // [id] route with id="1.2", not a static asset). See isInternalPath
    // above for the live measurement this carve-out closes.
    (pathname.includes(".") && !isInternalPath(pathname))
  ) {
    // Still add pathname header for consistency
    const response = NextResponse.next();
    response.headers.set("x-pathname", pathname);
    return response;
  }

  // Classify request for scraper detection
  const requestClass = classifyRequest(request);

  // Create response and add pathname header for Server Components
  const response = NextResponse.next();
  response.headers.set("x-pathname", pathname);

  // Tag suspicious requests on public content routes
  if (requestClass === "suspicious") {
    const firstSegment = pathname.split("/")[1];
    if (PUBLIC_CATEGORIES.includes(firstSegment) || pathname === "/news") {
      response.headers.set("X-Robots-Tag", "noindex");
      response.headers.set("x-request-class", "suspicious");
    }
  }

  // === REDIRECT 308: /kbli-navigator → /kbli ===
  // Legacy KBLI Navigator URL redirect (must be in middleware to take priority
  // over the (blog)/[category] catch-all route which would otherwise match first)
  if (
    pathname === "/kbli-navigator" ||
    pathname.startsWith("/kbli-navigator/")
  ) {
    const newPath = pathname.replace("/kbli-navigator", "/kbli") || "/kbli";
    const url = request.nextUrl.clone();
    url.pathname = newPath;
    return NextResponse.redirect(url, 308);
  }

  // === REDIRECT 301: mo.balizero.com → balizero.com ===
  // SEO: Prevent duplicate content and consolidate domain authority
  if (hostname === MOBILE_DOMAIN || hostname === `www.${MOBILE_DOMAIN}`) {
    const redirectUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
    redirectUrl.search = request.nextUrl.search;
    const redirectResponse = NextResponse.redirect(redirectUrl, 301); // Permanent redirect
    redirectResponse.headers.set("x-pathname", pathname);
    return redirectResponse;
  }

  // === REDIRECT 301: www.balizero.com → balizero.com (apex) ===
  // GSC export 2026-05-11 revealed ~50% of indexed URLs include `www.` prefix,
  // halving effective crawl budget. Vercel dashboard SHOULD be configured to
  // redirect www → apex at edge level (primary domain = balizero.com), but this
  // middleware safety-net catches any request that slips through (DNS cache,
  // Vercel config drift, manual links). See docs/marketing/spec-tax.md §6.
  if (hostname === `www.${PUBLIC_DOMAIN}`) {
    const redirectUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
    redirectUrl.search = request.nextUrl.search;
    const redirectResponse = NextResponse.redirect(redirectUrl, 301);
    redirectResponse.headers.set("x-pathname", pathname);
    return redirectResponse;
  }

  // Determine if we're on the public domain
  const subdomain = hostname.split(".")[0]; // e.g. "mail", "calendar", "kita", "balizero"
  const isSSOSubdomain = SSO_SUBDOMAINS.some((name) =>
    matchesDomain(hostname, `${name}.${PUBLIC_DOMAIN}`),
  );
  const isVisaDomain = matchesDomain(hostname, VISA_DOMAIN);
  const isTaxDomain = matchesDomain(hostname, TAX_DOMAIN);
  const isNuzantaraDomain = matchesDomain(hostname, NUZANTARA_DOMAIN);
  const isPublicDomain = matchesDomain(hostname, PUBLIC_DOMAIN);
  const isAppDomain =
    matchesDomain(hostname, APP_DOMAIN) ||
    isSSOSubdomain ||
    matchesDomain(hostname, `prime.${PUBLIC_DOMAIN}`);
  const isPortalDomain = matchesDomain(hostname, PORTAL_DOMAIN);

  // Development and Fly.dev: allow all routes (public-facing)
  const isDevelopment =
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  const isFlyDev = hostname === "fly.dev" || hostname.endsWith(".fly.dev");
  const enforceProdlikePortal =
    process.env.MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE === "1" &&
    isDevelopment &&
    isPortalPath(pathname);

  if (isDevelopment && !enforceProdlikePortal) {
    return response;
  }

  // isFlyDev is any public *.fly.dev hostname (a raw Vercel/Fly preview URL
  // reachable by anyone), not a development machine — unlike isDevelopment
  // above, it must still pass through the session gate.
  if (isFlyDev) {
    const gated = sessionGateRedirect(request, pathname);
    if (gated) return gated;
    return response;
  }

  // === PORTAL DOMAIN (my.balizero.com) ===
  if (isPortalDomain || enforceProdlikePortal) {
    // Portal domain: only allow /portal/* routes
    if (isPortalPath(pathname)) {
      if (PORTAL_PUBLIC_PATHS.has(pathname) || hasSession(request)) {
        return response;
      }

      // Stop anonymous deep links before the client layout calls the profile
      // API. Besides avoiding a visible loading flash, this prevents the
      // expected 401 from being reported as a browser console error.
      const redirectBase = enforceProdlikePortal
        ? `${request.nextUrl.protocol}//${request.headers.get("host")}`
        : request.url;
      const loginUrl = new URL("/portal/login-upgraded", redirectBase);
      loginUrl.searchParams.set(
        "redirect",
        `${pathname}${request.nextUrl.search}`,
      );
      const redirectResponse = NextResponse.redirect(loginUrl, 307);
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // Redirect root to portal login
    if (pathname === "/") {
      const redirectResponse = NextResponse.redirect(
        new URL("/portal/login", request.url),
      );
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // Redirect non-portal routes to public domain (with RSC/prefetch protection)
    const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
    publicUrl.search = request.nextUrl.search;
    return crossOriginRedirect(request, publicUrl);
  }

  // === ASSESSMENT DOMAIN (subhi.balizero.com) ===
  // Temporary assessment page for candidate — rewrites to /assessment/*
  if (
    hostname === ASSESSMENT_DOMAIN ||
    hostname === `www.${ASSESSMENT_DOMAIN}`
  ) {
    const rewriteUrl = request.nextUrl.clone();
    if (pathname === "/" || pathname === "") {
      rewriteUrl.pathname = "/assessment";
    } else if (!pathname.startsWith("/assessment")) {
      rewriteUrl.pathname = `/assessment${pathname}`;
    }
    const rewriteResponse = NextResponse.rewrite(rewriteUrl);
    rewriteResponse.headers.set("x-pathname", pathname);
    rewriteResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
    return rewriteResponse;
  }

  // === VISA DOMAIN (visa.balizero.com) — LEGACY, redirect to /visa ===
  // The visa funnel was consolidated at balizero.com/visa (see spec
  // 2026-04-21-visa-funnel-fusion.md). This block remaps legacy
  // Oracle subdomain paths 1:1 to the canonical /visa paths with a
  // temporary 302 so GSC can propagate the change of address. When
  // traffic drops to < 1% of peak for 30 days, the DNS record for
  // visa.balizero.com is removed entirely.
  if (isVisaDomain) {
    const target = new URL(request.url);
    target.hostname = "balizero.com";
    target.port = "";
    target.protocol = "https:";

    const legacy = pathname.replace(/\/+$/, "") || "/";
    const map: Record<string, string> = {
      "/": "/visa",
      "/quiz": "/visa/match",
      "/result": "/visa/match",
      "/chat": "/visa/match",
      "/privacy": "/visa/privacy",
      "/terms": "/visa/terms",
    };
    target.pathname = map[legacy] ?? "/visa";

    return NextResponse.redirect(target, 302);
  }

  // === TAX DOMAIN (tax.balizero.com) ===
  // Dedicated Tax Compliance Calendar webapp — rewrites all paths to /tax-calendar/* prefix.
  // The route group (tax-calendar) lives at /tax-calendar/* to avoid conflicts with existing routes.
  if (isTaxDomain) {
    const rewriteUrl = request.nextUrl.clone();
    if (pathname === "/" || pathname === "") {
      rewriteUrl.pathname = "/tax-calendar";
    } else if (!pathname.startsWith("/tax-calendar")) {
      rewriteUrl.pathname = `/tax-calendar${pathname}`;
    }
    const rewriteResponse = NextResponse.rewrite(rewriteUrl);
    rewriteResponse.headers.set("x-pathname", pathname);
    return rewriteResponse;
  }

  // === NUZANTARA DOMAIN (nuzantara.co.id) ===
  // Bahasa Indonesia holding page for the domestic brand, same shape as the
  // TAX DOMAIN block: every path is rewritten under the (nuzantara) route
  // group at /nuzantara/*. noindex until launch (docs/ops/nuzantara-co-id-dns-setup.md).
  if (isNuzantaraDomain) {
    const rewriteUrl = request.nextUrl.clone();
    if (pathname === "/" || pathname === "") {
      rewriteUrl.pathname = "/nuzantara";
    } else if (
      pathname !== "/nuzantara" &&
      !pathname.startsWith("/nuzantara/")
    ) {
      rewriteUrl.pathname = `/nuzantara${pathname}`;
    }
    const rewriteResponse = NextResponse.rewrite(rewriteUrl);
    rewriteResponse.headers.set("x-pathname", pathname);
    rewriteResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
    return rewriteResponse;
  }

  // === ZANTARA DOMAIN (zantara.balizero.com) ===
  // Dedicated Zantara AI chat webapp — rewrites root to /chat,
  // passes through /login and other routes untouched so auth redirects work.
  if (hostname === ZANTARA_DOMAIN || hostname === `www.${ZANTARA_DOMAIN}`) {
    if (pathname === "/") {
      const rewriteUrl = request.nextUrl.clone();
      rewriteUrl.pathname = "/chat";
      const rewriteResponse = NextResponse.rewrite(rewriteUrl);
      rewriteResponse.headers.set("x-pathname", pathname);
      rewriteResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
      return rewriteResponse;
    }
    // All other routes (/login, /api, etc.) pass through as-is — but only
    // after the same workspace session gate the APP DOMAIN block enforces.
    // This is the live leak the red-team found 2026-09-15T06:40Z: this
    // branch used to `return response` unconditionally, so
    // zantara.balizero.com/lkpm served the same anonymous 200 kita's /lkpm
    // used to, before round 1.
    const gated = sessionGateRedirect(request, pathname);
    if (gated) return gated;
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
    return response;
  }

  // === PUBLIC DOMAIN (balizero.com) ===
  if (isPublicDomain) {
    // Check if trying to access portal routes - redirect to portal domain
    if (pathname.startsWith("/portal")) {
      const portalUrl = new URL(pathname, `https://${PORTAL_DOMAIN}`);
      portalUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(portalUrl, 301); // Permanent redirect
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // Check if trying to access internal routes
    if (isInternalPath(pathname)) {
      // Redirect to app domain
      const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
      appUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(appUrl, 301);
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // Check if it's the /chat route - redirect to app
    if (pathname === "/chat" || pathname.startsWith("/chat/")) {
      const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
      appUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(appUrl, 301);
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // Rewrite /insights/* to /* for backward compatibility
    if (pathname.startsWith("/insights")) {
      const newPath = pathname.replace("/insights", "") || "/";
      const url = request.nextUrl.clone();
      url.pathname = newPath;
      const redirectResponse = NextResponse.redirect(url, 301);
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // === REDIRECT 301: Category renames (2026-03-23) ===
    const CATEGORY_REDIRECTS: Record<string, string> = {
      immigration: "visas",
      "tax-legal": "taxes",
      lifestyle: "living",
      tech: "trends",
      bali_news: "living",
      "digital-nomad": "living",
    };
    const oldCat = pathname.split("/")[1];
    if (oldCat && CATEGORY_REDIRECTS[oldCat]) {
      const newCat = CATEGORY_REDIRECTS[oldCat];
      const newPath = pathname.replace(`/${oldCat}`, `/${newCat}`);
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = newPath;
      return NextResponse.redirect(redirectUrl, 301);
    }

    // Allow public routes
    return response;
  }

  // === APP DOMAIN (kita.balizero.com) ===
  if (isAppDomain) {
    // prime.balizero.com → rewrite to /prime (keeps subdomain, no redirect)
    if (subdomain === "prime") {
      const rewritePath = pathname === "/" ? "/prime" : `/prime${pathname}`;
      const rewriteUrl = request.nextUrl.clone();
      rewriteUrl.pathname = rewritePath;
      return NextResponse.rewrite(rewriteUrl);
    }

    // Add X-Robots-Tag header to all responses from zantara subdomain
    response.headers.set("X-Robots-Tag", "noindex, nofollow");

    // Redirect portal routes to portal domain
    if (pathname.startsWith("/portal")) {
      const portalUrl = new URL(pathname, `https://${PORTAL_DOMAIN}`);
      portalUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(portalUrl, 301); // Permanent redirect
      redirectResponse.headers.set("x-pathname", pathname);
      redirectResponse.headers.set("X-Robots-Tag", "noindex, nofollow"); // Also noindex redirects
      return redirectResponse;
    }

    // Redirect root to login on app domain
    if (pathname === "/") {
      const redirectResponse = NextResponse.redirect(
        new URL("/login", request.url),
      );
      redirectResponse.headers.set("x-pathname", pathname);
      return redirectResponse;
    }

    // /email → the Zoho mailbox. Zoho has no path that corresponds to a kita
    // one, so /email and /email/<segment> both land on the inbox rather than
    // composing a path. A path containing a dot never reaches this middleware
    // at all — the matcher below excludes it — so /email/first.last 404s.
    if (pathname === "/email" || pathname.startsWith("/email/")) {
      return crossOriginRedirect(request, new URL(ZOHO_MAILBOX_URL), 302);
    }

    // Retired app routes go to the dashboard. Same reason the ghost-route
    // redirect below exists: without this they fall through to the
    // (blog)/[category] catch-all and render "Category not found".
    if (
      RETIRED_APP_ROUTES.some(
        (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
      )
    ) {
      const redirectResponse = NextResponse.redirect(
        new URL("/dashboard", request.url),
        302,
      );
      redirectResponse.headers.set("x-pathname", pathname);
      // Re-set what the app-domain block set on the response we are replacing:
      // a new response does not inherit it, and /calendar is not in robots.ts.
      redirectResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
      return redirectResponse;
    }

    // Redirect ghost internal routes (/knowledge) to their real standalone-app
    // subdomains. These paths have no route on kita and previously fell through
    // to the (blog)/[category] catch-all, rendering "Category not found" with
    // public nav instead of the actual app.
    for (const [routePrefix, targetHost] of Object.entries(
      APP_SUBDOMAIN_ROUTE_MAP,
    )) {
      if (pathname === routePrefix || pathname.startsWith(`${routePrefix}/`)) {
        const deepPath = pathname.slice(routePrefix.length) || "/";
        const targetUrl = new URL(deepPath, `https://${targetHost}`);
        targetUrl.search = request.nextUrl.search;
        // Cross-origin (kita → knowledge): route through crossOriginRedirect
        // so an RSC prefetch of <Link href="/knowledge"> gets 204 instead of a
        // cross-origin 302 that trips a console CORS error.
        return crossOriginRedirect(request, targetUrl, 302);
      }
    }

    // On app domain, redirect public content to main domain
    // Check if it's a category page (public content)
    const firstSegment = pathname.split("/")[1];

    if (PUBLIC_CATEGORIES.includes(firstSegment)) {
      // Redirect category pages to public domain (with RSC/prefetch protection)
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return crossOriginRedirect(request, publicUrl);
    }

    // Redirect /services to public domain (except API routes)
    if (
      pathname.startsWith("/services") &&
      !pathname.startsWith("/services/api")
    ) {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return crossOriginRedirect(request, publicUrl);
    }

    // Redirect /contact, /team, /news to public domain (with RSC/prefetch protection)
    if (
      pathname === "/contact" ||
      pathname === "/team" ||
      pathname === "/news" ||
      pathname.startsWith("/news/")
    ) {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return crossOriginRedirect(request, publicUrl);
    }

    // The gate that was missing entirely — see the comment above
    // sessionGateRedirect for the defect and the measurement. It sits LAST,
    // after every redirect already in this block (portal, root, /email,
    // RETIRED_APP_ROUTES, the /knowledge ghost-route map, PUBLIC_CATEGORIES,
    // /services, /contact /team /news), on purpose: each of those keeps its
    // exact current behaviour unchanged, and only the blanket allow below is
    // narrowed. That is what makes "no public route changes status" true by
    // construction, not by hope.
    const gated = sessionGateRedirect(request, pathname);
    if (gated) return gated;

    // Allow all other routes on app domain
    return response;
  }

  // Fall-through for any hostname no branch above classifies (e.g. a raw
  // Vercel deployment alias). Same reason as the isFlyDev and ZANTARA DOMAIN
  // call-sites above: this used to `return response` unconditionally, which
  // is the same "hand a gated path to rendering" action, just on a host
  // nobody named.
  const gatedFallthrough = sessionGateRedirect(request, pathname);
  if (gatedFallthrough) return gatedFallthrough;

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (images, etc)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*|api).*)",
    // The pattern above excludes EVERY dotted path, including a dynamic
    // segment value like /clients/1.2 — so Next never invoked this
    // middleware for it at all, no matter what isInternalPath said. Next
    // requires config.matcher to be statically analysable (literal strings,
    // not something built from INTERNAL_ROUTES at runtime), so this is a
    // second, hand-written copy of that array's prefixes, alternated over a
    // single path segment. workspace-session-gate.test.ts parses this string
    // back out and asserts it against INTERNAL_ROUTES in both directions —
    // add a route to one without the other and that test goes red.
    "/(accounting|admin|agents|analytics|clients|dashboard|garuda-voa|hr|intelligence|lkpm|login|notifications|obligations|omnichannel|partners|portal|process|review|second-home|settings|terminal)/:path*",
  ],
};

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Multi-domain Middleware
 *
 * Handles routing between:
 * - balizero.com (public website)
 * - kita.balizero.com (internal app)
 */

// Internal app routes that should only be on zantara subdomain
const INTERNAL_ROUTES = [
  "/login",
  "/dashboard",
  "/clients",
  "/process",
  "/documents",
  "/email",
  "/knowledge",
  "/settings",
  "/team-management", // workspace team management (not /team which is public)
  "/whatsapp",
  "/admin",
  "/agents",
  "/portal",
  "/analytics",
  "/intelligence",
  "/calendar",
  "/notifications",
];

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
// SSO subdomains: all *.balizero.com apps that share auth via cookie
const SSO_SUBDOMAINS = ["mail", "calendar", "drive", "knowledge"];

// Scraper detection — classify requests as human, welcome bot, or suspicious
const WELCOME_BOTS =
  /Googlebot|Bingbot|GPTBot|ClaudeBot|anthropic|PerplexityBot|Applebot|DuckDuckBot|Bytespider|Amazonbot|YouBot|FacebookBot|CCBot/i;
const SCRAPER_SIGNATURES =
  /python-requests|scrapy|curl\/|wget\/|Go-http-client|node-fetch|axios\/\d|PhantomJS|HeadlessChrome|Selenium|Nightmare|puppeteer/i;

/**
 * Detect RSC/prefetch requests that should NOT be cross-origin redirected.
 * Next.js Link prefetches trigger RSC fetches; redirecting these cross-origin
 * causes CORS errors that flood the console and slow down the page.
 */
function isRSCOrPrefetch(request: NextRequest): boolean {
  return (
    request.nextUrl.searchParams.has("_rsc") ||
    request.headers.get("RSC") === "1" ||
    request.headers.get("Next-Router-Prefetch") === "1" ||
    request.headers.get("Purpose") === "prefetch"
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

export function middleware(request: NextRequest) {
  const hostname = request.headers.get("host") || "";
  const pathname = request.nextUrl.pathname;

  // Skip static files and API routes
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/static") ||
    pathname.includes(".") // files with extensions
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

  // Determine if we're on the public domain
  const subdomain = hostname.split(".")[0]; // e.g. "mail", "calendar", "kita", "balizero"
  const isSSOSubdomain = SSO_SUBDOMAINS.includes(subdomain);
  const isVisaDomain =
    hostname.includes("visa.balizero") || hostname === VISA_DOMAIN;
  const isPublicDomain =
    hostname.includes(PUBLIC_DOMAIN) &&
    !hostname.includes("kita") &&
    !hostname.includes("my") &&
    !hostname.includes("visa") &&
    !isSSOSubdomain &&
    subdomain !== "prime";
  const isAppDomain =
    hostname.includes(APP_DOMAIN) ||
    (hostname.includes("kita") && !hostname.includes("my")) ||
    isSSOSubdomain ||
    subdomain === "prime";
  const isPortalDomain =
    hostname.includes(PORTAL_DOMAIN) || hostname.includes("my.balizero.com");

  // Development and Fly.dev: allow all routes (public-facing)
  const isDevelopment =
    hostname.includes("localhost") || hostname.includes("127.0.0.1");
  const isFlyDev = hostname.includes("fly.dev");

  if (isDevelopment || isFlyDev) {
    return response;
  }

  // === PORTAL DOMAIN (my.balizero.com) ===
  if (isPortalDomain) {
    // Portal domain: only allow /portal/* routes
    if (pathname.startsWith("/portal")) {
      // Allow portal routes
      return response;
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

  // === VISA DOMAIN (visa.balizero.com) ===
  // Dedicated Visa Oracle webapp — rewrites all paths to /visa-oracle/* prefix.
  // The route group (visa-oracle) lives at /visa-oracle/* to avoid conflicts
  // with existing routes (/chat, /privacy, /terms etc).
  if (isVisaDomain) {
    const rewriteUrl = request.nextUrl.clone();
    if (pathname === "/" || pathname === "") {
      rewriteUrl.pathname = "/visa-oracle";
    } else if (!pathname.startsWith("/visa-oracle")) {
      rewriteUrl.pathname = `/visa-oracle${pathname}`;
    }
    const rewriteResponse = NextResponse.rewrite(rewriteUrl);
    rewriteResponse.headers.set("x-pathname", pathname);
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
      return rewriteResponse;
    }
    // All other routes (/login, /api, etc.) pass through as-is
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
    const isInternalRoute = INTERNAL_ROUTES.some(
      (route) => pathname === route || pathname.startsWith(`${route}/`),
    );

    if (isInternalRoute) {
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
    // === SSO SUBDOMAINS (mail/calendar/drive/knowledge.balizero.com) ===
    // These subdomains don't have their own routes — redirect to kita.balizero.com
    // with the appropriate deep-link path. Auth is handled by kita's workspace layout
    // which reads the httpOnly cookie shared across .balizero.com.
    if (isSSOSubdomain) {
      // Map subdomain → internal route on kita
      const subdomainRouteMap: Record<string, string> = {
        mail: "/email",
        calendar: "/calendar",
        drive: "/documents",
        knowledge: "/knowledge",
      };
      const targetRoute = subdomainRouteMap[subdomain] || "/dashboard";
      // Preserve any path after the root (e.g. calendar.balizero.com/event/123 → /calendar/event/123)
      const deepPath =
        pathname === "/" ? targetRoute : `${targetRoute}${pathname}`;
      const kitaUrl = new URL(deepPath, `https://${APP_DOMAIN}`);
      kitaUrl.search = request.nextUrl.search;
      return NextResponse.redirect(kitaUrl, 302);
    }

    // prime.balizero.com → rewrite to /prime (keeps subdomain, no redirect)
    if (subdomain === "prime") {
      const rewritePath = pathname === "/" ? "/prime" : `/prime${pathname}`;
      const rewriteUrl = request.nextUrl.clone();
      rewriteUrl.pathname = rewritePath;
      return NextResponse.rewrite(rewriteUrl);
    }

    // SEO: Block indexing for zantara subdomain (internal app)
    // robots.txt override
    if (pathname === "/robots.txt") {
      return new NextResponse("User-agent: *\nDisallow: /", {
        headers: {
          "Content-Type": "text/plain",
          "Cache-Control": "public, max-age=3600",
        },
      });
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

    // Allow all other routes on app domain
    return response;
  }

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
  ],
};

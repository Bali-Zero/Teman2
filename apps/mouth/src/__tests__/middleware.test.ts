import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "../proxy";

/**
 * Helper to create NextRequest with proper host header
 * NextRequest in test environment doesn't automatically set host header from URL
 */
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

describe("Middleware - Multi-domain Routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Static Files and API Routes", () => {
    it("should skip middleware for _next static files", () => {
      const request = createRequest(
        "https://balizero.com/_next/static/chunk.js",
      );
      const response = proxy(request);

      expect(response.headers.get("x-pathname")).toBe("/_next/static/chunk.js");
    });

    it("should skip middleware for API routes", () => {
      const request = createRequest("https://balizero.com/api/auth/login");
      const response = proxy(request);

      expect(response.headers.get("x-pathname")).toBe("/api/auth/login");
    });

    it("should skip middleware for files with extensions", () => {
      const request = createRequest("https://balizero.com/favicon.ico");
      const response = proxy(request);

      expect(response.headers.get("x-pathname")).toBe("/favicon.ico");
    });
  });

  describe("Mobile Domain Redirect (mo.balizero.com)", () => {
    it("should redirect mo.balizero.com to balizero.com with 301", () => {
      const request = createRequest(
        "https://mo.balizero.com/immigration/kitas",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/immigration/kitas",
      );
    });

    it("should redirect www.mo.balizero.com to balizero.com", () => {
      const request = createRequest("https://www.mo.balizero.com/business");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/business",
      );
    });

    it("should preserve query parameters in mobile redirect", () => {
      const request = createRequest(
        "https://mo.balizero.com/services?category=visa",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/services?category=visa",
      );
    });
  });

  describe("Development and Fly.dev Environments", () => {
    it("should allow all routes on localhost", () => {
      const request = createRequest("http://localhost:3000/dashboard");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/dashboard");
    });

    it("should allow all routes on 127.0.0.1", () => {
      const request = createRequest("http://127.0.0.1:3000/login");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get("x-pathname")).toBe("/login");
    });

    it("should allow all routes on fly.dev", () => {
      const request = createRequest("https://app.fly.dev/clients");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get("x-pathname")).toBe("/clients");
    });
  });

  describe("Portal Domain (my.balizero.com)", () => {
    it("should allow /portal routes on portal domain", () => {
      const request = createRequest("https://my.balizero.com/portal/dashboard");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/portal/dashboard");
    });

    it("should redirect root to /portal/login on portal domain", () => {
      const request = createRequest("https://my.balizero.com/");
      const response = proxy(request);

      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toContain("/portal/login");
    });

    it("should redirect non-portal routes to public domain", () => {
      const request = createRequest(
        "https://my.balizero.com/immigration/kitas",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/immigration/kitas",
      );
    });

    it("should preserve query params when redirecting from portal domain", () => {
      const request = createRequest(
        "https://my.balizero.com/services?type=visa",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/services?type=visa",
      );
    });
  });

  describe("Public Domain (balizero.com)", () => {
    it("should redirect /portal routes to portal domain with 301", () => {
      const request = createRequest("https://balizero.com/portal/dashboard");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://my.balizero.com/portal/dashboard",
      );
    });

    it("should redirect /login to app domain", () => {
      const request = createRequest("https://balizero.com/login");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/login",
      );
    });

    it("should redirect /dashboard to app domain", () => {
      const request = createRequest("https://balizero.com/dashboard");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/dashboard",
      );
    });

    it("should redirect /clients to app domain", () => {
      const request = createRequest("https://balizero.com/clients");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/clients",
      );
    });

    it("should redirect /chat to app domain", () => {
      const request = createRequest("https://balizero.com/chat");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/chat",
      );
    });

    it("should redirect /admin to app domain", () => {
      const request = createRequest("https://balizero.com/admin");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/admin",
      );
    });

    it("should redirect /insights/* to root path for backward compatibility", () => {
      const request = createRequest(
        "https://balizero.com/insights/immigration",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toContain("/immigration");
    });

    it("should allow public category routes", () => {
      // Use a non-redirected category (visas is the canonical name after rename)
      const request = createRequest("https://balizero.com/visas/kitas");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/visas/kitas");
    });

    it("should allow /services routes", () => {
      const request = createRequest(
        "https://balizero.com/services/visa-assistance",
      );
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get("x-pathname")).toBe(
        "/services/visa-assistance",
      );
    });

    it("should allow /contact route", () => {
      const request = createRequest("https://balizero.com/contact");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get("x-pathname")).toBe("/contact");
    });

    it("should preserve query params when redirecting internal routes", () => {
      const request = createRequest(
        "https://balizero.com/dashboard?tab=analytics",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/dashboard?tab=analytics",
      );
    });
  });

  describe("App Domain (kita.balizero.com)", () => {
    it("should redirect /portal routes to portal domain with 301", () => {
      const request = createRequest(
        "https://kita.balizero.com/portal/documents",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://my.balizero.com/portal/documents",
      );
    });

    it("should redirect root to /login on app domain", () => {
      const request = createRequest("https://kita.balizero.com/");
      const response = proxy(request);

      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toContain("/login");
    });

    it("should redirect public category pages to public domain", () => {
      const request = createRequest(
        "https://kita.balizero.com/immigration/kitas",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/immigration/kitas",
      );
    });

    it("should redirect /services to public domain", () => {
      const request = createRequest("https://kita.balizero.com/services");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/services",
      );
    });

    it("should allow /services/api routes on app domain", () => {
      const request = createRequest(
        "https://kita.balizero.com/services/api/endpoint",
      );
      const response = proxy(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/services/api/endpoint");
    });

    it("should redirect /contact to public domain", () => {
      const request = createRequest("https://kita.balizero.com/contact");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/contact",
      );
    });

    it("should redirect /team to public domain", () => {
      const request = createRequest("https://kita.balizero.com/team");
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/team",
      );
    });

    it("should allow /team-management on app domain", () => {
      const request = createRequest(
        "https://kita.balizero.com/team-management",
      );
      const response = proxy(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/team-management");
    });

    it("should allow internal app routes", () => {
      const request = createRequest("https://kita.balizero.com/dashboard");
      const response = proxy(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/dashboard");
    });

    it("should allow /clients route", () => {
      const request = createRequest("https://kita.balizero.com/clients");
      const response = proxy(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/clients");
    });

    it("should allow /whatsapp route", () => {
      const request = createRequest("https://kita.balizero.com/whatsapp");
      const response = proxy(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/whatsapp");
    });

    it("should preserve query params when redirecting to public domain", () => {
      const request = createRequest(
        "https://kita.balizero.com/immigration?lang=en",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/immigration?lang=en",
      );
    });
  });

  describe("Pathname Header", () => {
    it("should always set x-pathname header", () => {
      // Use a non-redirected route (visas is canonical after category rename)
      const request = createRequest("https://balizero.com/visas/kitas");
      const response = proxy(request);

      expect(response.headers.get("x-pathname")).toBe("/visas/kitas");
    });

    it("should set x-pathname header even for redirects on public domain", () => {
      const request = createRequest("https://balizero.com/login");
      const response = proxy(request);

      expect(response.headers.get("x-pathname")).toBe("/login");
      expect(response.status).toBe(301);
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing host header gracefully", () => {
      const request = new NextRequest("https://balizero.com/test");
      // Don't set host header - simulates missing header

      expect(() => proxy(request)).not.toThrow();
    });

    it("should handle nested internal routes on public domain", () => {
      const request = createRequest(
        "https://balizero.com/dashboard/analytics/reports",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/dashboard/analytics/reports",
      );
    });

    it("should handle chat subroutes on public domain", () => {
      const request = createRequest(
        "https://balizero.com/chat/conversation/123",
      );
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://kita.balizero.com/chat/conversation/123",
      );
    });

    it("should allow chat subroutes on localhost", () => {
      const request = createRequest(
        "http://localhost:3000/chat/conversation/123",
      );
      const response = proxy(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get("x-pathname")).toBe("/chat/conversation/123");
    });
  });

  // =======================================================================
  // SSO subdomain classification: mail/calendar/drive/knowledge.balizero.com
  // are standalone apps (their own Vercel deploys) that mouth never actually
  // serves — but if a request for one of them ever does reach this
  // middleware, it must be classified as app-domain (noindex, no public-nav
  // treatment), never as public marketing content.
  // =======================================================================
  describe("SSO subdomain classification (isAppDomain, not isPublicDomain)", () => {
    const ssoHosts = [
      "mail.balizero.com",
      "calendar.balizero.com",
      "drive.balizero.com",
      "knowledge.balizero.com",
    ];

    for (const host of ssoHosts) {
      it(`sets X-Robots-Tag noindex on ${host} (app-domain treatment, not public)`, () => {
        // Use a non-root path: "/" hits the root->login redirect, which
        // returns before X-Robots-Tag is set on that particular response.
        const request = createRequest(`https://${host}/inbox`);
        const response = proxy(request);

        expect(response.headers.get("X-Robots-Tag")).toBe("noindex, nofollow");
      });
    }

    it("[innocence] a lookalike public path (balizero.com/mail) stays public, uncontaminated", () => {
      const request = createRequest("https://balizero.com/mail");
      const response = proxy(request);

      expect(response.headers.get("X-Robots-Tag")).not.toBe(
        "noindex, nofollow",
      );
    });
  });

  // =======================================================================
  // Ghost internal routes (/email, /calendar, /knowledge, /documents) →
  // real standalone-app subdomains. These paths have no route on kita and
  // used to fall through to the (blog)/[category] catch-all.
  // =======================================================================
  describe("Ghost internal routes redirect to standalone app subdomains", () => {
    const cases: Array<[string, string]> = [
      ["/email", "https://mail.balizero.com/"],
      ["/calendar", "https://calendar.balizero.com/"],
      ["/knowledge", "https://knowledge.balizero.com/"],
      ["/documents", "https://drive.balizero.com/"],
    ];

    for (const [from, to] of cases) {
      it(`redirects 302 kita.balizero.com${from} → ${to}`, () => {
        const request = createRequest(`https://kita.balizero.com${from}`);
        const response = proxy(request);

        expect(response.status).toBe(302);
        expect(response.headers.get("location")).toBe(to);
      });
    }

    it("preserves deep path and query when redirecting /calendar/event/123", () => {
      const request = createRequest(
        "https://kita.balizero.com/calendar/event/123?tab=details",
      );
      const response = proxy(request);

      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe(
        "https://calendar.balizero.com/event/123?tab=details",
      );
    });

    it("does not redirect unrelated app-domain routes (e.g. /dashboard)", () => {
      const request = createRequest("https://kita.balizero.com/dashboard");
      const response = proxy(request);

      expect(response.status).not.toBe(302);
      expect(response.headers.get("x-pathname")).toBe("/dashboard");
    });

    // The ghost-route redirect is cross-origin (kita → mail/calendar/...), so
    // an RSC prefetch of <Link href="/email"> must get 204, not a 302 that
    // trips a console CORS error. The original ghost-route block redirected
    // manually and skipped the RSC guard — this pins that it no longer does.
    it("[guilt] returns 204 for an RSC prefetch of a ghost route (/email)", () => {
      const request = createRequest("https://kita.balizero.com/email", {
        accept: "text/x-component",
      });
      const response = proxy(request);

      expect(response.status).toBe(204);
    });

    it("[innocence] still 302-redirects a real navigation to /email", () => {
      const request = createRequest("https://kita.balizero.com/email", {
        accept: "text/html,application/xhtml+xml",
      });
      const response = proxy(request);

      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe(
        "https://mail.balizero.com/",
      );
    });
  });

  // =======================================================================
  // RSC/prefetch detection (CORS console-error fix): the `_rsc` query param
  // and `RSC`/`Next-Router-Prefetch` headers are stripped by Next.js before
  // middleware runs in production, so `Accept: text/x-component` is the only
  // signal that survives — this pair proves the fix is neither too broad nor
  // too narrow.
  // =======================================================================
  describe("RSC/prefetch detection via Accept header", () => {
    it("[guilt] returns 204 (not 301) for a real RSC fetch on a cross-origin redirect", () => {
      const request = createRequest("https://kita.balizero.com/contact", {
        accept: "text/x-component",
      });
      const response = proxy(request);

      expect(response.status).toBe(204);
    });

    it("[innocence] still returns 301 for a real browser navigation (Accept: text/html)", () => {
      const request = createRequest("https://kita.balizero.com/contact", {
        accept: "text/html,application/xhtml+xml",
      });
      const response = proxy(request);

      expect(response.status).toBe(301);
      expect(response.headers.get("location")).toBe(
        "https://balizero.com/contact",
      );
    });
  });

  // =======================================================================
  // visa.balizero.com → balizero.com/visa (spec 2026-04-21-visa-funnel-fusion)
  // 1:1 302 redirects so GSC change-of-address propagates cleanly; after
  // 30d of near-zero traffic, DNS is removed and this block stops firing.
  // =======================================================================
  describe("visa.balizero.com legacy subdomain redirects", () => {
    const cases: Array<[string, string]> = [
      ["/", "/visa"],
      ["/quiz", "/visa/match"],
      ["/result", "/visa/match"],
      ["/chat", "/visa/match"],
      ["/privacy", "/visa/privacy"],
      ["/terms", "/visa/terms"],
      ["/random-unmapped-path", "/visa"],
    ];

    for (const [from, to] of cases) {
      it(`redirects 302 ${from} → balizero.com${to}`, () => {
        const req = createRequest(`https://visa.balizero.com${from}`);
        const res = proxy(req);
        expect(res.status).toBe(302);
        const location = res.headers.get("location")!;
        const url = new URL(location);
        expect(url.hostname).toBe("balizero.com");
        expect(url.pathname).toBe(to);
      });
    }
  });
});

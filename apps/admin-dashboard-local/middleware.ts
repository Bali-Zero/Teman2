/**
 * Cockpit middleware — origin localhost gate + PIN cookie gate.
 *
 * Defense in depth: next.config.mjs already refuses to start without
 * LOCAL_ONLY=1. This middleware enforces the same invariant at request
 * time so even if the binary is somehow exposed it refuses non-loopback
 * traffic.
 *
 * Cookie gate: every /cockpit and /api/cockpit path requires the
 * `zantara_cockpit_session` cookie EXCEPT POST/GET /api/cockpit/auth
 * which is the gate's own endpoint. Real bcrypt verification + HMAC
 * audit log happens in /api/cockpit/auth/route.ts.
 */
import { NextRequest, NextResponse } from "next/server";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

function isLoopback(req: NextRequest): boolean {
  // Prefer the Host header for the literal authority the client used.
  const host = req.headers.get("host") ?? "";
  const stripped = host.split(":")[0].trim().toLowerCase();
  if (
    !LOOPBACK_HOSTS.has(stripped) &&
    !LOOPBACK_HOSTS.has(host.toLowerCase())
  ) {
    return false;
  }
  // Block forwarded traffic (reverse proxies, tunnels). Localhost-only.
  if (req.headers.get("x-forwarded-host")) return false;
  if (req.headers.get("x-forwarded-for")) return false;
  return true;
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (!isLoopback(req)) {
    return new NextResponse(
      JSON.stringify({ error: "non-loopback origin refused" }),
      { status: 403, headers: { "content-type": "application/json" } },
    );
  }

  // The auth endpoint itself MUST be reachable without the cookie.
  if (pathname.startsWith("/api/cockpit/auth")) {
    return NextResponse.next();
  }

  const session = req.cookies.get("zantara_cockpit_session");
  if (!session?.value) {
    if (pathname.startsWith("/api/")) {
      return new NextResponse(JSON.stringify({ error: "unauthenticated" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }
    // For HTML pages we let the PinGate component show the modal; we still
    // pass the request through so the page can render the gate UI.
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/cockpit/:path*", "/api/cockpit/:path*"],
};

import { NextResponse, type NextRequest } from "next/server";
import { isAllowedCockpitHost } from "@/lib/cockpit-host";
import { hasValidCockpitSession } from "@/lib/cockpit-session";

export const config = {
  matcher: [
    "/cockpit/:path*",
    "/garuda-voa/:path*",
    "/api/cockpit/:path*",
    "/api/garuda-voa/:path*",
    "/api/llm-costs/recommendations",
  ],
};

const PRIVATE_HEADERS = {
  "cache-control": "no-store, max-age=0",
  "x-robots-tag": "noindex, nofollow, noarchive",
};

export async function middleware(req: NextRequest) {
  if (!isAllowedCockpitHost(req.headers.get("host"))) {
    return new NextResponse("Forbidden: cockpit is localhost-only", {
      status: 403,
      headers: PRIVATE_HEADERS,
    });
  }
  const isAuthRoute = req.nextUrl.pathname === "/api/cockpit/auth";
  const isProtectedApi =
    req.nextUrl.pathname.startsWith("/api/cockpit/") ||
    req.nextUrl.pathname.startsWith("/api/garuda-voa/") ||
    req.nextUrl.pathname === "/api/llm-costs/recommendations";
  const hasSession = isAuthRoute ? false : await hasValidCockpitSession(req);
  if (!isAuthRoute && isProtectedApi && !hasSession) {
    return NextResponse.json(
      { error: "unauthorized" },
      { status: 401, headers: PRIVATE_HEADERS },
    );
  }

  const response = NextResponse.next();
  for (const [key, value] of Object.entries(PRIVATE_HEADERS)) {
    response.headers.set(key, value);
  }
  return response;
}

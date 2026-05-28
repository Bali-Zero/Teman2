import { NextResponse, type NextRequest } from "next/server";

export const config = {
  matcher: ["/cockpit/:path*", "/api/cockpit/:path*"],
};

const VALID_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function middleware(req: NextRequest) {
  const host = req.headers.get("host")?.split(":")[0] ?? "";
  if (!VALID_HOSTS.has(host)) {
    return new NextResponse("Forbidden: cockpit is localhost-only", {
      status: 403,
    });
  }
  const isAuthRoute = req.nextUrl.pathname === "/api/cockpit/auth";
  const pinCookie = req.cookies.get("cockpit-session")?.value;
  if (!isAuthRoute && !pinCookie) {
    if (req.nextUrl.pathname.startsWith("/api/cockpit/")) {
      return new NextResponse(JSON.stringify({ error: "unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }
  }
  return NextResponse.next();
}

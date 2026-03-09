import { NextRequest, NextResponse } from "next/server";

/**
 * mail.balizero.com middleware
 *
 * SSO strategy: the nz_access_token cookie (Domain=.balizero.com, httpOnly)
 * should be sent by the browser to this subdomain automatically.
 * Edge middleware reads it from request.cookies reliably.
 *
 * If cookie present → allow.
 * If missing → redirect to kita login with redirect-back URL.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip static assets
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const token = request.cookies.get("nz_access_token");

  if (!token?.value) {
    return NextResponse.redirect(
      "https://kita.balizero.com/login?redirect=https://mail.balizero.com",
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};

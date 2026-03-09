import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const token = request.cookies.get("nz_access_token");
  if (!token?.value) {
    const returnTo = encodeURIComponent(
      `https://calendar.balizero.com${pathname}${request.nextUrl.search}`,
    );
    return NextResponse.redirect(
      `https://kita.balizero.com/login?redirect=${returnTo}`,
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};

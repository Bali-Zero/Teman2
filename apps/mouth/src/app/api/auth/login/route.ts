import { NextRequest, NextResponse } from "next/server";
import { logger } from "@/lib/logger";

function getBackendUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://nuzantara-rag.fly.dev";
  // Normalize: strip trailing slash and /api suffix to get base URL
  return raw
    .trim()
    .replace(/\/+$/, "")
    .replace(/\/api$/, "");
}
const BACKEND_URL = getBackendUrl();

export async function POST(req: NextRequest): Promise<NextResponse> {
  try {
    const body = await req.json();

    // Call backend server-side (no CORS restriction)
    const upstream = await fetch(`${BACKEND_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await upstream.json();

    if (!upstream.ok || !data?.data?.token) {
      return NextResponse.json(data, { status: upstream.status });
    }

    const { expiresIn } = data.data;
    // Strip whitespace/newlines — backend may include trailing \n in token values
    const token = String(data.data.token).replace(/\s+/g, "");
    const csrfToken = data.data.csrfToken
      ? String(data.data.csrfToken).replace(/\s+/g, "")
      : undefined;
    // Strip any whitespace/newlines from env var values
    const requestHostname = req.nextUrl.hostname.toLowerCase();
    const isLoopback = ["localhost", "127.0.0.1", "::1"].includes(
      requestHostname,
    );
    const isProdlikeLoopback =
      process.env.MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE === "1" && isLoopback;
    const cookieDomain = isProdlikeLoopback
      ? ""
      : (
          process.env.COOKIE_DOMAIN ||
          (process.env.NODE_ENV === "production" ? ".balizero.com" : "")
        ).replace(/\s+/g, "");
    const domainAttribute = cookieDomain ? `; Domain=${cookieDomain}` : "";
    const maxAge = expiresIn || 86400;
    const isSecure =
      process.env.NODE_ENV === "production" && !isProdlikeLoopback;

    // Build cookie attributes — all values explicitly stripped of whitespace
    const secure = isSecure ? "; Secure" : "";
    const tokenCookie =
      `nz_access_token=${token}` +
      domainAttribute +
      `; HttpOnly` +
      `; Max-Age=${maxAge}` +
      `; Path=/` +
      `; SameSite=Lax` +
      secure;
    const csrfCookieStr = csrfToken
      ? `nz_csrf_token=${csrfToken}` +
        domainAttribute +
        `; Max-Age=${maxAge}` +
        `; Path=/` +
        `; SameSite=Lax` +
        secure
      : null;

    logger.info("Login successful, cookies set", {
      component: "LoginRoute",
      action: "login",
    });

    // Build headers as array of tuples to avoid any Headers.append newline issues
    const headerTuples: [string, string][] = [
      ["content-type", "application/json"],
      ["set-cookie", tokenCookie],
    ];
    if (csrfCookieStr) headerTuples.push(["set-cookie", csrfCookieStr]);

    return new Response(
      JSON.stringify({ success: true, message: data.message, data: data.data }),
      { status: 200, headers: headerTuples },
    ) as unknown as NextResponse;
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    logger.error(
      "Login route error",
      {
        component: "LoginRoute",
        action: "login",
        metadata: { errMsg, backendUrl: BACKEND_URL },
      },
      error instanceof Error ? error : new Error(String(error)),
    );
    return NextResponse.json(
      { success: false, message: "Internal server error", debug: errMsg },
      { status: 500 },
    );
  }
}

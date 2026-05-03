import { NextRequest, NextResponse } from "next/server";
import { logger } from "@/lib/logger";

function getBackendUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://nuzantara-rag.fly.dev";
  // Normalize: strip trailing slash and /api suffix to get base URL
  return raw.replace(/\/+$/, "").replace(/\/api$/, "");
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

    const { user, expiresIn } = data.data;
    // Strip whitespace/newlines — backend may include trailing \n in token values
    const token = String(data.data.token).replace(/\s+/g, "");
    const csrfToken = data.data.csrfToken
      ? String(data.data.csrfToken).replace(/\s+/g, "")
      : undefined;
    // Strip any whitespace/newlines from env var values
    const cookieDomain = (
      process.env.COOKIE_DOMAIN ||
      (process.env.NODE_ENV === "production" ? ".balizero.com" : "localhost")
    ).replace(/\s+/g, "");
    const maxAge = expiresIn || 86400;
    const isSecure = process.env.NODE_ENV === "production";

    // Build cookie attributes — all values explicitly stripped of whitespace
    const secure = isSecure ? "; Secure" : "";
    const tokenCookie =
      `nz_access_token=${token}` +
      `; Domain=${cookieDomain}` +
      `; HttpOnly` +
      `; Max-Age=${maxAge}` +
      `; Path=/` +
      `; SameSite=Lax` +
      secure;
    const csrfCookieStr = csrfToken
      ? `nz_csrf_token=${csrfToken}` +
        `; Domain=${cookieDomain}` +
        `; Max-Age=${maxAge}` +
        `; Path=/` +
        `; SameSite=Lax` +
        secure
      : null;

    logger.info("Login successful, cookies set", {
      component: "LoginRoute",
      action: "login",
      user: user?.email,
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

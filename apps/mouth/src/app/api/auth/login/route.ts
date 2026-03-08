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

    const { token, csrfToken, user, expiresIn } = data.data;
    const cookieDomain =
      process.env.COOKIE_DOMAIN ||
      (process.env.NODE_ENV === "production" ? ".balizero.com" : "localhost");
    const maxAge = expiresIn || 86400;
    const isSecure = process.env.NODE_ENV === "production";

    // Build raw Set-Cookie header strings (no newlines — bypasses NextResponse.cookies.set() bug)
    const respHeaders = new Headers();
    const tokenCookieParts = [
      `nz_access_token=${token}`,
      `Domain=${cookieDomain}`,
      `HttpOnly`,
      `Max-Age=${maxAge}`,
      `Path=/`,
      `SameSite=Lax`,
    ];
    if (isSecure) tokenCookieParts.push("Secure");
    respHeaders.append("set-cookie", tokenCookieParts.join("; "));

    if (csrfToken) {
      const csrfCookieParts = [
        `nz_csrf_token=${csrfToken}`,
        `Domain=${cookieDomain}`,
        `Max-Age=${maxAge}`,
        `Path=/`,
        `SameSite=Lax`,
      ];
      if (isSecure) csrfCookieParts.push("Secure");
      respHeaders.append("set-cookie", csrfCookieParts.join("; "));
    }

    // Build response with proper cookies
    const resp = NextResponse.json(
      { success: true, message: data.message, data: data.data },
      { status: 200, headers: respHeaders },
    );

    logger.info("Login successful, cookies set", {
      component: "LoginRoute",
      action: "login",
      user: user?.email,
    });

    return resp;
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

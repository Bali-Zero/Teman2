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

    const { token, csrfToken, user, token_type, expiresIn, redirectTo } =
      data.data;
    const cookieDomain =
      process.env.COOKIE_DOMAIN ||
      (process.env.NODE_ENV === "production" ? ".balizero.com" : "localhost");
    const maxAge = expiresIn || 86400;

    // Build response with proper cookies
    const resp = NextResponse.json(
      { success: true, message: data.message, data: data.data },
      { status: 200 },
    );

    // Set httpOnly auth cookie — shared across *.balizero.com
    resp.cookies.set({
      name: "nz_access_token",
      value: token,
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge,
      path: "/",
      domain: cookieDomain,
    });

    if (csrfToken) {
      resp.cookies.set({
        name: "nz_csrf_token",
        value: csrfToken,
        httpOnly: false,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge,
        path: "/",
        domain: cookieDomain,
      });
    }

    logger.info("Login successful, cookies set", {
      component: "LoginRoute",
      action: "login",
      user: user?.email,
    });

    return resp;
  } catch (error) {
    logger.error(
      "Login route error",
      { component: "LoginRoute", action: "login" },
      error instanceof Error ? error : new Error(String(error)),
    );
    return NextResponse.json(
      { success: false, message: "Internal server error" },
      { status: 500 },
    );
  }
}

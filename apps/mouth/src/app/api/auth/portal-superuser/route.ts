import { NextRequest, NextResponse } from "next/server";
import { logger } from "@/lib/logger";

// Server-side probe for the portal sign-in page: may the signed-in account use
// the client portal as a superuser? The public login bundle may only name
// `/api/auth/*` routes (scripts/assert-public-login-bundle.mjs), so the
// backend's `/api/portal/admin/me` is reached from here, never from the page.
// The answer is a boolean about the caller and nothing else; every failure —
// no session, upstream error, timeout — reads as "no".

function getBackendUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://nuzantara-rag.fly.dev";
  return raw
    .trim()
    .replace(/\/+$/, "")
    .replace(/\/api$/, "");
}
const BACKEND_URL = getBackendUrl();
const UPSTREAM_TIMEOUT_MS = 5_000;

function sessionToken(req: NextRequest): string | null {
  const header = req.headers.get("authorization") ?? "";
  const bearer = header.match(/^Bearer\s+(\S+)$/i)?.[1];
  if (bearer) return bearer;
  const cookie = req.cookies.get("nz_access_token")?.value?.trim();
  return cookie || null;
}

function answer(isSuperuser: boolean): NextResponse {
  return NextResponse.json(
    { success: true, is_superuser: isSuperuser },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  const token = sessionToken(req);
  if (!token) return answer(false);

  try {
    const upstream = await fetch(`${BACKEND_URL}/api/portal/admin/me`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (!upstream.ok) return answer(false);
    const body = (await upstream.json().catch(() => null)) as {
      is_superuser?: unknown;
    } | null;
    return answer(body?.is_superuser === true);
  } catch (error) {
    logger.warn(
      "Portal superuser probe failed upstream",
      { component: "PortalSuperuserRoute", action: "GET" },
      error instanceof Error ? error : undefined,
    );
    return answer(false);
  }
}

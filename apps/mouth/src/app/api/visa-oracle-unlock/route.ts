/**
 * Visa Oracle internal PIN unlock (server-side).
 *
 * POST   { pin } -> sets the signed `vo_internal` cookie on success (401 on a
 *                   wrong PIN, 503 when no PIN is configured — fail-closed).
 * DELETE          -> clears the cookie ("lock it again" / end of a test).
 *
 * Deliberately NOT under `/api/visa-oracle/*`: that prefix is proxied to the
 * backend by the `[...path]` catch-all, and this route must never leave the
 * frontend. The PIN is compared here and NEVER forwarded upstream, so it
 * cannot reach backend logs.
 *
 * This is a soft internal gate, not authentication — see `internal-access.ts`
 * for the honest threat model (its strength is the PIN's entropy, no more).
 */
import { NextRequest, NextResponse } from "next/server";
import {
  INTERNAL_ACCESS_COOKIE,
  INTERNAL_ACCESS_MAX_AGE_SECONDS,
  configuredPin,
  mintInternalAccessToken,
  safeEquals,
  verifyInternalAccessToken,
} from "@/app/(visa-oracle)/visa-oracle/_lib/internal-access";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function isSecureRequest(req: NextRequest): boolean {
  const hostname = req.nextUrl.hostname.toLowerCase();
  const isLoopback = ["localhost", "127.0.0.1", "::1"].includes(hostname);
  return process.env.NODE_ENV === "production" && !isLoopback;
}

/**
 * Host-only cookie (no `Domain`): the Oracle is served from one host, and
 * Vercel's Edge runtime is documented in `api/[...path]/route.ts` to silently
 * drop `Set-Cookie` headers carrying `domain=.balizero.com`.
 */
function buildCookie(req: NextRequest, value: string, maxAge: number): string {
  const secure = isSecureRequest(req) ? "; Secure" : "";
  return `${INTERNAL_ACCESS_COOKIE}=${value}; Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Lax${secure}`;
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const pin = configuredPin();
  if (pin === null) {
    // Fail-closed: an unset env var must never mean "everyone is internal".
    return NextResponse.json(
      { ok: false, error: "NOT_CONFIGURED" },
      { status: 503 },
    );
  }

  let presented = "";
  try {
    const body: unknown = await req.json();
    if (body !== null && typeof body === "object" && "pin" in body) {
      const raw = (body as { pin: unknown }).pin;
      if (typeof raw === "string") presented = raw.trim();
    }
  } catch {
    // Malformed JSON is just a failed attempt; never echo the parse error.
  }

  // Never log the presented value, not even truncated.
  if (presented.length === 0 || !safeEquals(presented, pin)) {
    return NextResponse.json(
      { ok: false, error: "INVALID_PIN" },
      { status: 401 },
    );
  }

  const expiresAtMs = Date.now() + INTERNAL_ACCESS_MAX_AGE_SECONDS * 1000;
  const response = NextResponse.json({ ok: true });
  response.headers.set(
    "Set-Cookie",
    buildCookie(
      req,
      mintInternalAccessToken(pin, expiresAtMs),
      INTERNAL_ACCESS_MAX_AGE_SECONDS,
    ),
  );
  return response;
}

/**
 * Status probe for the client shell: "is this browser unlocked?".
 *
 * Kept as an endpoint (rather than reading the cookie in the page's server
 * component) so `/visa-oracle` — a PUBLIC page — stays statically rendered
 * instead of becoming per-request dynamic. The answer is still computed
 * server-side from the signed cookie; the browser only learns a boolean.
 */
export async function GET(req: NextRequest): Promise<NextResponse> {
  const token = req.cookies.get(INTERNAL_ACCESS_COOKIE)?.value;
  const response = NextResponse.json({
    internal: verifyInternalAccessToken(token),
    configured: configuredPin() !== null,
  });
  response.headers.set("Cache-Control", "no-store, private");
  return response;
}

export async function DELETE(req: NextRequest): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  response.headers.set("Set-Cookie", buildCookie(req, "", 0));
  return response;
}

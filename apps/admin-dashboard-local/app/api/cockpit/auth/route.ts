/**
 * POST /api/cockpit/auth — verify PIN, set httpOnly session cookie (12h).
 * GET  /api/cockpit/auth — probe current session (used by PinGate UI).
 *
 * Read-only outcome: writes only to cockpit_audit_log via HMAC chain. The
 * cookie is the SOLE proof of auth; in-memory rate limit (lib/cockpit-auth)
 * enforces 5 failures / 5 min lockout per client IP.
 */
import { NextRequest, NextResponse } from "next/server";
import {
  verifyPin,
  recordFailure,
  isLockedOut,
  resetRateLimit,
  readPinHash,
} from "@/lib/cockpit-auth";
import { insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";

export const dynamic = "force-dynamic";

const COOKIE_NAME = "zantara_cockpit_session";
const COOKIE_TTL_S = 12 * 60 * 60;

function clientId(req: NextRequest): string {
  // Localhost only, but rate-limit per source IP anyway in case the
  // user runs multiple shells / browser profiles against the same dev
  // server.
  return (
    req.headers.get("x-real-ip") ||
    req.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    "loopback"
  );
}

export async function GET(req: NextRequest) {
  const session = req.cookies.get(COOKIE_NAME);
  return NextResponse.json({ authenticated: Boolean(session?.value) });
}

export async function POST(req: NextRequest) {
  const id = clientId(req);

  if (isLockedOut(id)) {
    return NextResponse.json(
      { error: "locked out — try again in 5 minutes" },
      { status: 429 },
    );
  }

  let body: { pin?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }
  const pin = typeof body.pin === "string" ? body.pin : "";
  if (!pin) {
    return NextResponse.json({ error: "missing pin" }, { status: 400 });
  }

  const hash = readPinHash();
  if (!hash) {
    return NextResponse.json(
      {
        error: "cockpit PIN not configured — run scripts/setup-cockpit-pin.sh",
      },
      { status: 503 },
    );
  }

  const ok = await verifyPin(pin, hash);
  const hmacSecret = readHmacSecret();

  if (!ok) {
    recordFailure(id);
    if (hmacSecret) {
      try {
        await insertAuditRow(hmacSecret, {
          action: "cockpit.auth.failure",
          params: { client_id: id },
          result: "denied",
        });
      } catch {
        // Audit failures must not block the auth response.
      }
    }
    return NextResponse.json({ error: "wrong pin" }, { status: 401 });
  }

  resetRateLimit(id);
  if (hmacSecret) {
    try {
      await insertAuditRow(hmacSecret, {
        action: "cockpit.auth.success",
        params: { client_id: id },
        result: "success",
      });
    } catch {
      // ignore
    }
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, "1", {
    httpOnly: true,
    sameSite: "strict",
    secure: false, // localhost only
    path: "/",
    maxAge: COOKIE_TTL_S,
  });
  return res;
}

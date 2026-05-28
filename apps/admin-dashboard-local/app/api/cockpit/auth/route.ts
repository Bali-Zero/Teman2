import { NextRequest, NextResponse } from "next/server";
import {
  verifyPin,
  recordFailure,
  isLockedOut,
  readPinHash,
  resetRateLimit,
} from "@/lib/cockpit-auth";
import { insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const clientId = req.headers.get("x-forwarded-for") ?? "localhost";
  const hmacSecret = readHmacSecret();

  if (isLockedOut(clientId)) {
    if (hmacSecret) {
      await insertAuditRow(hmacSecret, {
        action: "auth.pin",
        params: {},
        result: "denied",
        errorMessage: "rate-limited",
      });
    }
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });
  }

  const body = await req.json().catch(() => ({}));
  const pin = typeof body.pin === "string" ? body.pin : "";
  const pinHash = readPinHash();
  if (!pinHash) {
    return NextResponse.json(
      { error: "pin_not_configured", hint: "run scripts/setup-cockpit-pin.sh" },
      { status: 503 },
    );
  }

  const ok = await verifyPin(pin, pinHash);
  if (hmacSecret) {
    await insertAuditRow(hmacSecret, {
      action: "auth.pin",
      params: {},
      result: ok ? "success" : "denied",
    });
  }

  if (!ok) {
    recordFailure(clientId);
    return NextResponse.json({ error: "invalid_pin" }, { status: 401 });
  }

  resetRateLimit(clientId);
  const res = NextResponse.json({ ok: true });
  res.cookies.set("cockpit-session", "1", {
    httpOnly: true,
    sameSite: "strict",
    secure: false,
    maxAge: 60 * 60 * 12,
    path: "/",
  });
  return res;
}

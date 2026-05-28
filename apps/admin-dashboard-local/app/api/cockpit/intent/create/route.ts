import { NextRequest, NextResponse } from "next/server";
import { createIntent, insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";
import { isLockedOut, recordFailure } from "@/lib/cockpit-auth";

export const dynamic = "force-dynamic";

const ALLOWED = new Set([
  "intel.skip",
  "intel.rerun",
  "wr2.approve",
  "wr2.reject",
  "cron.kill",
  "library.approve-pr",
  "library.reject-pr",
]);

export async function POST(req: NextRequest) {
  const clientId = req.headers.get("x-forwarded-for") ?? "localhost";
  if (isLockedOut(clientId)) {
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });
  }

  const body = await req.json().catch(() => ({}));
  const intentType =
    typeof body.intent_type === "string" ? body.intent_type : "";
  const params =
    typeof body.params === "object" && body.params !== null ? body.params : {};
  const reason = typeof body.reason === "string" ? body.reason : "";

  if (!ALLOWED.has(intentType)) {
    recordFailure(clientId);
    return NextResponse.json(
      { error: "invalid_intent_type", intentType },
      { status: 400 },
    );
  }
  if (!reason || reason.length < 5) {
    return NextResponse.json(
      { error: "reason_required_min_5_chars" },
      { status: 400 },
    );
  }

  const hmacSecret = readHmacSecret();
  try {
    const intentId = await createIntent(intentType, params, reason);
    if (hmacSecret) {
      await insertAuditRow(hmacSecret, {
        action: `intent.${intentType}`,
        params: { ...params, intent_id: intentId.toString() },
        result: "success",
      });
    }
    return NextResponse.json({ ok: true, intent_id: intentId.toString() });
  } catch (e: any) {
    if (hmacSecret) {
      await insertAuditRow(hmacSecret, {
        action: `intent.${intentType}`,
        params,
        result: "error",
        errorMessage: e.message,
      });
    }
    return NextResponse.json(
      { error: "intent_create_failed" },
      { status: 500 },
    );
  }
}

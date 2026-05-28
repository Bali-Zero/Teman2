import { NextRequest, NextResponse } from "next/server";
import { isAgenticCronLabel } from "@/lib/cockpit-allowlist";
import { startCron } from "@/lib/cockpit-launchctl";
import { insertAuditRow } from "@/lib/cockpit-pg";
import { readHmacSecret } from "@/lib/cockpit-audit";
import { isLockedOut, recordFailure } from "@/lib/cockpit-auth";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const clientId = req.headers.get("x-forwarded-for") ?? "localhost";
  if (isLockedOut(clientId)) {
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });
  }

  const body = await req.json().catch(() => ({}));
  const label = typeof body.label === "string" ? body.label : "";
  const reason = typeof body.reason === "string" ? body.reason : "";

  if (!isAgenticCronLabel(label)) {
    recordFailure(clientId);
    return NextResponse.json(
      { error: "not_in_allowlist", label },
      { status: 403 },
    );
  }
  if (!reason || reason.length < 5) {
    return NextResponse.json(
      { error: "reason_required_min_5_chars" },
      { status: 400 },
    );
  }

  const hmacSecret = readHmacSecret();
  const result = await startCron(label);
  if (hmacSecret) {
    await insertAuditRow(hmacSecret, {
      action: "cron.run",
      params: { label, reason },
      result: result.ok ? "success" : "error",
      errorMessage: result.stderr,
    });
  }
  if (!result.ok) {
    return NextResponse.json(
      { error: "launchctl_failed", stderr: result.stderr },
      { status: 500 },
    );
  }
  return NextResponse.json({ ok: true, label });
}

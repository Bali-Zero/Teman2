import { NextRequest, NextResponse } from "next/server";
import {
  verifyPassphrase,
  completePassphraseAttempt,
  isLockedOut,
  readPassphraseHash,
  reservePassphraseAttempt,
  resetRateLimit,
} from "@/lib/cockpit-auth";
import { insertAuditRow } from "@/lib/cockpit-pg";
import {
  COCKPIT_SESSION_MAX_AGE_SECONDS,
  createCockpitSessionToken,
  readCockpitHmacKey,
} from "@/lib/cockpit-session";
import { isAllowedCockpitHost } from "@/lib/cockpit-host";
import { sameOriginJsonFailure } from "@/lib/cockpit-request-guard";

export const dynamic = "force-dynamic";

const PRIVATE_HEADERS = {
  "cache-control": "no-store, max-age=0",
  "x-robots-tag": "noindex, nofollow, noarchive",
};

function privateJson(body: unknown, status: number = 200) {
  return NextResponse.json(body, { status, headers: PRIVATE_HEADERS });
}

async function writeAuthAudit(
  hmacSecret: string,
  result: "success" | "denied",
  errorMessage?: string,
): Promise<boolean> {
  try {
    await insertAuditRow(hmacSecret, {
      action: "auth.passphrase",
      // Authentication audit records never contain the passphrase, request
      // body, or any GARUDA case payload.
      params: {},
      result,
      errorMessage,
    });
    return true;
  } catch {
    return false;
  }
}

export async function POST(req: NextRequest) {
  if (!isAllowedCockpitHost(req.headers.get("host"))) {
    return privateJson({ error: "forbidden" }, 403);
  }
  const guardFailure = sameOriginJsonFailure(req);
  if (guardFailure) {
    return privateJson({ error: guardFailure.error }, guardFailure.status);
  }

  const hmacSecret = readCockpitHmacKey();

  if (!hmacSecret) {
    return privateJson({ error: "cockpit_session_key_unavailable" }, 503);
  }

  if (isLockedOut()) {
    // A logging outage must not turn a locked request into an auth bypass.
    await writeAuthAudit(hmacSecret, "denied", "rate-limited");
    return privateJson({ error: "rate_limited" }, 429);
  }

  const body = await req.json().catch(() => ({}));
  const passphrase = typeof body.passphrase === "string" ? body.passphrase : "";
  const passphraseHash = readPassphraseHash();
  if (!passphraseHash) {
    return privateJson({ error: "passphrase_not_configured" }, 503);
  }

  const reservation = reservePassphraseAttempt();
  if (!reservation) {
    await writeAuthAudit(hmacSecret, "denied", "rate-limited");
    return privateJson({ error: "rate_limited" }, 429);
  }
  const ok = await verifyPassphrase(passphrase, passphraseHash);
  completePassphraseAttempt(reservation, ok);

  if (!ok) {
    // Completion updates the bounded memory guard before awaiting I/O. A
    // failed audit write cannot erase or postpone this denial.
    await writeAuthAudit(hmacSecret, "denied");
    return privateJson({ error: "invalid_pin" }, 401);
  }

  // Successful login is fail-closed on audit durability: no session is
  // issued unless the empty-payload authentication event was recorded.
  if (!(await writeAuthAudit(hmacSecret, "success"))) {
    return privateJson({ error: "audit_unavailable" }, 503);
  }

  resetRateLimit();
  const sessionToken = await createCockpitSessionToken(hmacSecret);
  return privateJson({
    token: sessionToken,
    expires_in: COCKPIT_SESSION_MAX_AGE_SECONDS,
  });
}

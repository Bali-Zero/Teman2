import { NextRequest, NextResponse } from "next/server";
import {
  verifyPassphrase,
  completePassphraseAttempt,
  isLockedOut,
  readPassphraseHash,
  reservePassphraseAttempt,
  resetRateLimit,
} from "@/lib/cockpit-auth";
import {
  COCKPIT_SESSION_MAX_AGE_SECONDS,
  createCockpitSessionToken,
  readCockpitSessionKey,
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

export async function POST(req: NextRequest) {
  if (!isAllowedCockpitHost(req.headers.get("host"))) {
    return privateJson({ error: "forbidden" }, 403);
  }
  const guardFailure = sameOriginJsonFailure(req);
  if (guardFailure) {
    return privateJson({ error: guardFailure.error }, guardFailure.status);
  }

  const sessionSecret = readCockpitSessionKey();

  if (!sessionSecret) {
    return privateJson({ error: "cockpit_session_key_unavailable" }, 503);
  }

  if (isLockedOut()) {
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
    return privateJson({ error: "rate_limited" }, 429);
  }
  const ok = await verifyPassphrase(passphrase, passphraseHash);
  completePassphraseAttempt(reservation, ok);

  if (!ok) {
    return privateJson({ error: "invalid_pin" }, 401);
  }

  resetRateLimit();
  const sessionToken = await createCockpitSessionToken(
    sessionSecret,
    req.nextUrl.origin,
  );
  return privateJson({
    token: sessionToken,
    expires_in: COCKPIT_SESSION_MAX_AGE_SECONDS,
  });
}

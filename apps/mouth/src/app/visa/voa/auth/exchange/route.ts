import { NextRequest } from "next/server";
import { isGarudaVoaPublicEnabled } from "../../flag";
import { logger } from "@/lib/logger";
import {
  ACCOUNT_COOKIE_PREFIX,
  FAILURE_LOCATION,
  PENDING_COOKIE,
  PENDING_COOKIE_PATH,
  RESULT_ID_PATTERN,
  TOKEN_MAX_LENGTH,
  TOKEN_MIN_LENGTH,
  isLoopback,
} from "../contract";

/**
 * `POST /visa/voa/auth/exchange` — the only place in this app that redeems a
 * GARUDA VOA magic-link token.
 *
 * The token arrives in the HttpOnly `garuda_magic_pending` cookie that
 * `../route.ts` set, NOT in the form body: nothing in the page the customer
 * saw ever held it (see that file for why — the root layout's Google
 * Analytics reads `window.location.href` on every page).
 *
 * Reached only by the form's POST, never a GET, so a mail scanner's
 * unsolicited prefetch of the emailed link cannot burn the single-use token.
 *
 * THE FLAG IS RE-CHECKED HERE ON PURPOSE. `../../layout.tsx` gates every PAGE
 * under `/visa/voa/**` with `notFound()`, but Next does not run layouts for
 * route handlers — without this check, this handler would be the one VOA
 * surface alive in production while the whole funnel is meant to be dark.
 *
 * IT CALLS THE BACKEND THROUGH THIS APP'S OWN `/api` PROXY, not the Fly host
 * directly. Two reasons, both measured: (1) the proxy at
 * `src/app/api/[...path]/route.ts:421,449,510` forwards the upstream
 * `Set-Cookie` verbatim for every path except `/api/auth/login` — verified
 * live on 2026-08-28, `garuda_result_session` arrives at the browser through
 * `balizero.com` — so the account cookie needs no re-derivation here and
 * cannot drift from the attributes the backend intends
 * (`_set_account_session_cookie` reads `get_cookie_domain()` and
 * `get_samesite_policy()` at runtime). (2) It avoids duplicating the proxy's
 * backend-base resolution, whose `normalizeBackendBaseUrl` strips a trailing
 * `/api` — so the browser-facing default `NEXT_PUBLIC_API_URL=/api`
 * normalises to the empty string, which is fine for the proxy (it always has
 * `NUZANTARA_API_URL` in prod) and would be an unfetchable relative URL here.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Clears the pending cookie. Same Path, or the browser keeps the old one. */
function expirePending(secure: boolean): string {
  return [
    `${PENDING_COOKIE}=`,
    "HttpOnly",
    `Path=${PENDING_COOKIE_PATH}`,
    "Max-Age=0",
    "SameSite=Lax",
    ...(secure ? ["Secure"] : []),
  ].join("; ");
}

function seeOther(location: string, cookies: string[]): Response {
  const headers = new Headers({
    Location: location,
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
  });
  for (const c of cookies) headers.append("set-cookie", c);
  return new Response(null, { status: 303, headers });
}

export async function POST(request: NextRequest): Promise<Response> {
  if (!isGarudaVoaPublicEnabled()) {
    return new Response(null, { status: 404 });
  }

  const secure = !isLoopback(new URL(request.url).hostname);
  // The token is spent (or was never valid) by the time we answer, so the
  // pending cookie is cleared on EVERY path out of here — success, refusal,
  // and malformed alike. Leaving it behind would keep a live credential in
  // the browser after the one gesture it existed for.
  const clear = expirePending(secure);

  const magicToken = request.cookies.get(PENDING_COOKIE)?.value;

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return seeOther(FAILURE_LOCATION, [clear]);
  }
  const resultId = form.get("result_id");

  if (
    typeof magicToken !== "string" ||
    magicToken.length < TOKEN_MIN_LENGTH ||
    magicToken.length > TOKEN_MAX_LENGTH ||
    typeof resultId !== "string" ||
    !RESULT_ID_PATTERN.test(resultId)
  ) {
    return seeOther(FAILURE_LOCATION, [clear]);
  }

  // `Idempotency-Key` is mandatory on the exchange and must match
  // `^[A-Za-z0-9._~-]{16,200}$`. `randomUUID()` satisfies that charset. A
  // FRESH key per submission is correct: a same-key replay returns 204 with
  // no `Set-Cookie`, so reusing one would hand back a redirect with no
  // session — the silent failure this route exists to prevent.
  const target = new URL("/api/visa/voa/auth/sessions", request.url);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ token: magicToken }),
      cache: "no-store",
    });
  } catch {
    // Never log the token or the URL that carries it.
    logger.error("[garuda-voa-auth] magic-link exchange transport failure", {
      component: "AUTO",
      action: "error",
    });
    return seeOther(FAILURE_LOCATION, [clear]);
  }

  if (upstream.status !== 204) {
    logger.info("[garuda-voa-auth] magic-link exchange refused", {
      component: "AUTO",
      action: "denied",
      metadata: { status: upstream.status },
    });
    return seeOther(FAILURE_LOCATION, [clear]);
  }

  // `getSetCookie()` — NOT `get("set-cookie")`. A single-value read folds
  // multiple cookies into one comma-joined string and the browser then
  // stores none of them correctly.
  const forwarded = upstream.headers.getSetCookie();

  // Check the NAME, not merely that SOME cookie came back (adversarial
  // review, 2026-08-28). A 204 with no session cookie is the documented
  // replay outcome, and if the backend ever adds an unrelated cookie on that
  // path a length check would pass it and land an unauthenticated visitor on
  // the authenticated upload page.
  if (!forwarded.some((c) => c.startsWith(ACCOUNT_COOKIE_PREFIX))) {
    logger.warn(
      "[garuda-voa-auth] exchange returned 204 with no account session cookie",
      { component: "AUTO", action: "warn" },
    );
    return seeOther(FAILURE_LOCATION, [clear]);
  }

  return seeOther(`/visa/voa/upload/${encodeURIComponent(resultId)}`, [
    ...forwarded,
    clear,
  ]);
}

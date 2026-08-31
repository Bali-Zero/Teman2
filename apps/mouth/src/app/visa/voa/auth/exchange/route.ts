import { NextRequest } from "next/server";
import { isGarudaVoaPublicEnabled } from "../../flag";
import { logger } from "@/lib/logger";
import {
  FAILURE_LOCATION,
  PENDING_COOKIE,
  PENDING_COOKIE_PATH,
  decodePending,
  hasAccountSession,
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
 * Only `POST` is exported, so a mail scanner's unsolicited GET/HEAD/prefetch
 * of the emailed link cannot burn the single-use token. A POST is NOT proof
 * of a human gesture, though — a cookie-preserving sandbox that follows the
 * 303 and submits the form would redeem it (council finding, Codex sol
 * 2026-08-28, accepted as residual: the alternative is a challenge in front
 * of every emailed link). What it does buy is that no PASSIVE fetch spends
 * the token.
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
  const secure = !isLoopback(new URL(request.url).hostname);
  // The token is spent (or was never valid) by the time we answer, so the
  // pending cookie is cleared on EVERY path out of here — success, refusal,
  // malformed, AND flag-off. This is computed before the flag gate on
  // purpose: an earlier version returned 404 first and left a live credential
  // sitting in the browser, while the comment above it claimed "every path"
  // (council finding, Codex sol 2026-08-28 — the comment was the bug).
  const clear = expirePending(secure);

  if (!isGarudaVoaPublicEnabled()) {
    return new Response(null, {
      status: 404,
      headers: { "Cache-Control": "no-store", "set-cookie": clear },
    });
  }

  // The POST must be provably same-origin. `SameSite=Lax` on the pending
  // cookie stops an ordinary cross-site POST but NOT one from a sibling
  // subdomain, which is same-site — and this app shares `balizero.com` with
  // several.
  //
  // `Sec-Fetch-Site` is browser-set and unforgeable by page JS, so it is the
  // primary signal. ABSENT is not treated as same-origin, but it is not an
  // automatic refusal either: Safari only shipped the header in 16.4, and some
  // in-app mail webviews still omit it — and an EMAILED link is exactly the
  // entry point that lands in a webview, so refusing on absence alone would
  // silently tell real customers their link is invalid (adversarial review
  // 2026-08-28). Those clients do send `Origin` on a POST, and a sibling
  // subdomain's `Origin` is a DIFFERENT origin, so the fallback closes the
  // same vector without the false refusals.
  const site = request.headers.get("sec-fetch-site");
  const originHeader = request.headers.get("origin");
  const sameOrigin =
    site === "same-origin" ||
    (site === null && originHeader === new URL(request.url).origin);
  if (!sameOrigin) {
    logger.info("[garuda-voa-auth] exchange refused: not same-origin", {
      component: "AUTO",
      action: "denied",
    });
    return seeOther(FAILURE_LOCATION, [clear]);
  }

  // BOTH halves come from the one cookie, and the form body is not read at
  // all — it carries no fields. See `../contract.ts` on why the result id
  // stopped being a hidden input.
  const pending = decodePending(request.cookies.get(PENDING_COOKIE)?.value);
  if (pending === null) {
    return seeOther(FAILURE_LOCATION, [clear]);
  }
  const { resultId, token: magicToken } = pending;

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

  // Check the NAME *and* a non-empty VALUE (adversarial review 2026-08-28,
  // then both council seats independently). A 204 with no session cookie is
  // the documented replay outcome; an unrelated cookie would satisfy a mere
  // length check; and `garuda_session=` with an empty value is a DELETION
  // that satisfies a name-prefix check. All three would land an
  // unauthenticated visitor on the authenticated upload page.
  if (!hasAccountSession(forwarded)) {
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

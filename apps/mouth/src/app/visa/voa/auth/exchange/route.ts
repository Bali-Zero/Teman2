import { NextRequest } from "next/server";
import { isGarudaVoaPublicEnabled } from "../../flag";
import { logger } from "@/lib/logger";

/**
 * `POST /visa/voa/auth/exchange` — the only place in this app that redeems a
 * GARUDA VOA magic-link token.
 *
 * It is reached by the plain HTML form on `../page.tsx`, never by a GET, so a
 * mail scanner's unsolicited prefetch cannot burn the single-use token (see
 * that page's header for why that matters).
 *
 * THE FLAG IS RE-CHECKED HERE ON PURPOSE. `../layout.tsx` gates every PAGE
 * under `/visa/voa/**` with `notFound()`, but Next does not run layouts for
 * route handlers — without this check, this handler would be the one VOA
 * surface alive in production while the whole funnel is meant to be dark.
 *
 * IT CALLS THE BACKEND THROUGH THIS APP'S OWN `/api` PROXY, not the Fly host
 * directly. Two reasons, both measured: (1) the proxy at
 * `src/app/api/[...path]/route.ts` already forwards the upstream
 * `Set-Cookie` verbatim for every path except `/api/auth/login` — verified
 * live on 2026-08-28, `garuda_result_session` arrives at the browser through
 * `balizero.com` — so the account cookie needs no re-derivation here and
 * cannot drift from the attributes the backend intends
 * (`_set_account_session_cookie` reads `get_cookie_domain()` and
 * `get_samesite_policy()` at runtime; anything reconstructed client-side
 * would be a copy that silently goes stale). (2) It avoids duplicating the
 * proxy's backend-base resolution, whose `normalizeBackendBaseUrl` strips a
 * trailing `/api` — so the browser-facing default `NEXT_PUBLIC_API_URL=/api`
 * normalises to the empty string, which is fine for the proxy (it always has
 * `NUZANTARA_API_URL` in prod) and would be an unfetchable relative URL here.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const RESULT_ID_PATTERN = /^[A-Za-z0-9_-]{22,128}$/;
const TOKEN_MIN_LENGTH = 32;
const TOKEN_MAX_LENGTH = 2048;

/** Landing page for every failure. Deliberately uniform: the backend answers
 * one non-enumerating 401 for invalid / expired / already-used tokens
 * (DECISIONS.md Q1), and this handler must not re-introduce the distinction
 * the backend went out of its way to erase. The token is NOT echoed back into
 * the redirect — that is the whole point of getting it out of the URL. */
const FAILURE_LOCATION = "/visa/voa/auth?error=invalid";

function seeOther(location: string, setCookies: string[] = []): Response {
  const headers = new Headers({
    Location: location,
    "Cache-Control": "no-store",
  });
  for (const cookie of setCookies) {
    headers.append("set-cookie", cookie);
  }
  return new Response(null, { status: 303, headers });
}

export async function POST(request: NextRequest): Promise<Response> {
  if (!isGarudaVoaPublicEnabled()) {
    return new Response(null, { status: 404 });
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return seeOther(FAILURE_LOCATION);
  }

  const magicToken = form.get("magic_token");
  const resultId = form.get("result_id");

  if (
    typeof magicToken !== "string" ||
    magicToken.length < TOKEN_MIN_LENGTH ||
    magicToken.length > TOKEN_MAX_LENGTH ||
    typeof resultId !== "string" ||
    !RESULT_ID_PATTERN.test(resultId)
  ) {
    return seeOther(FAILURE_LOCATION);
  }

  // `Idempotency-Key` is mandatory on the exchange and must match
  // `^[A-Za-z0-9._~-]{16,200}$`. `randomUUID()` satisfies that charset. A
  // FRESH key per submission is correct here: a same-key replay returns 204
  // with no `Set-Cookie`, so reusing one would hand back a redirect with no
  // session — the exact silent failure this route exists to prevent.
  const idempotencyKey = crypto.randomUUID();
  const target = new URL("/api/visa/voa/auth/sessions", request.url);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
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
    return seeOther(FAILURE_LOCATION);
  }

  if (upstream.status !== 204) {
    logger.info("[garuda-voa-auth] magic-link exchange refused", {
      component: "AUTO",
      action: "denied",
      metadata: { status: upstream.status },
    });
    return seeOther(FAILURE_LOCATION);
  }

  // `getSetCookie()` — NOT `get("set-cookie")`. A single-value read folds
  // multiple cookies into one comma-joined string and the browser then
  // stores none of them correctly.
  const setCookies = upstream.headers.getSetCookie();
  if (setCookies.length === 0) {
    // A 204 with no cookie is the documented replay outcome. It is not a
    // signed-in state, so it must not look like one.
    logger.warn(
      "[garuda-voa-auth] exchange returned 204 with no session cookie",
      {
        component: "AUTO",
        action: "warn",
      },
    );
    return seeOther(FAILURE_LOCATION);
  }

  return seeOther(
    `/visa/voa/upload/${encodeURIComponent(resultId)}`,
    setCookies,
  );
}

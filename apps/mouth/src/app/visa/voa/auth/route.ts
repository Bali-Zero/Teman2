import { NextRequest } from "next/server";
import { isGarudaVoaPublicEnabled } from "../flag";
import {
  FAILURE_LOCATION,
  PENDING_COOKIE,
  PENDING_COOKIE_MAX_AGE_SECONDS,
  PENDING_COOKIE_PATH,
  RESULT_ID_PATTERN,
  TOKEN_MAX_LENGTH,
  TOKEN_MIN_LENGTH,
  isLoopback,
} from "./contract";

/**
 * `GET /visa/voa/auth` — where the emailed magic link lands. It renders NO
 * document: it moves the token out of the URL into an HttpOnly cookie and
 * redirects to `./continue`, which is the page a human actually sees.
 *
 * WHY A REDIRECT AND NOT A PAGE (corrected 2026-08-28 after adversarial
 * review — the first version of this route WAS a page, and it leaked):
 * `apps/mouth/src/app/layout.tsx:289` renders `<GoogleAnalytics>` and
 * `<RouteChangeTracker>` in the app's single root layout, so every page
 * inherits them. GA4's bootstrap `gtag('config', ...)` sends an automatic
 * `page_view` whose default `page_location` is `document.location.href` —
 * the full URL, query string included — and `RouteChangeTracker` sends
 * `page_location: window.location.href` explicitly. Measured the same day:
 * `G-S3H2M6VXWT` and `googletagmanager.com/gtag/js` are live in the HTML
 * balizero.com serves. So a PAGE at this URL ships the customer's single-use
 * credential to Google before they touch anything — and nothing inside the
 * page's own code prevents it, because GA reads the browser's location, not
 * the page's props.
 *
 * A route handler runs no layout, loads no script and returns no document.
 * The token URL therefore produces no analytics beacon and nothing in the
 * DOM; the page the customer sees carries only `result_id`. That closes the
 * same hole for any future third-party tag and for the client Sentry SDK,
 * instead of patching one vendor.
 *
 * Residual, deliberately accepted and NOT claimed closed: the token is in
 * the URL of this one first-party request, so it can appear in Vercel's
 * access log and in a server-side Sentry transaction. That is inherent to
 * any emailed link; what this route removes is the third-party and
 * client-side exposure.
 *
 * The flag is checked HERE because Next does not run layouts for route
 * handlers — `../layout.tsx`'s `notFound()` does not cover this file.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function seeOther(location: string, cookie?: string): Response {
  const headers = new Headers({
    Location: location,
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
  });
  if (cookie) headers.append("set-cookie", cookie);
  return new Response(null, { status: 303, headers });
}

export async function GET(request: NextRequest): Promise<Response> {
  if (!isGarudaVoaPublicEnabled()) {
    return new Response(null, { status: 404 });
  }

  const url = new URL(request.url);
  const magicToken = url.searchParams.get("magic_token");
  const resultId = url.searchParams.get("result_id");

  const usable =
    magicToken !== null &&
    magicToken.length >= TOKEN_MIN_LENGTH &&
    magicToken.length <= TOKEN_MAX_LENGTH &&
    resultId !== null &&
    RESULT_ID_PATTERN.test(resultId);

  if (!usable) {
    return seeOther(FAILURE_LOCATION);
  }

  const cookie = [
    `${PENDING_COOKIE}=${encodeURIComponent(magicToken)}`,
    "HttpOnly",
    `Path=${PENDING_COOKIE_PATH}`,
    `Max-Age=${PENDING_COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
    ...(isLoopback(url.hostname) ? [] : ["Secure"]),
  ].join("; ");

  return seeOther(
    `/visa/voa/auth/continue?result_id=${encodeURIComponent(resultId)}`,
    cookie,
  );
}

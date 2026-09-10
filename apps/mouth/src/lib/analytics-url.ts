/**
 * Credential-bearing query parameters must never reach a third-party
 * analytics endpoint.
 *
 * Measured 2026-09-11 (live network capture on my.balizero.com, portal audit
 * finding L-GA / ux F8): opening `/portal/register?token=…` or
 * `/portal/magic?token=…` produced
 * `POST https://www.google-analytics.com/g/collect?…&dl=<the full URL, token
 * included>` → **HTTP 204**. Google accepted the single-use invite token and
 * the single-use magic-link token verbatim, in `page_location`, before the
 * client had touched anything. The invalid-token case leaked a second time as
 * `dr=` (referrer) after the auto-redirect to `/portal/login-upgraded?…
 * redirect=%2Fportal%2Fmagic%3Ftoken%3D…`. `www.google-analytics.com` is
 * whitelisted in the portal's `connect-src`, so nothing on the page blocked it.
 *
 * GA reads `document.location.href`, not the page's props, so no per-page code
 * can prevent this — the value has to be overridden before the first beacon
 * fires. `analyticsUrlRedactScript` does that in `<head>` (before gtag.js
 * loads) and `redactSensitiveQueryParams` does it for every explicit
 * `page_view` this app sends itself.
 *
 * This is defence in depth, not a substitute for keeping tokens out of URLs:
 * `src/app/visa/voa/auth/route.ts` shows the structural fix (a route handler
 * that moves the token into an HttpOnly cookie and redirects to a URL that
 * carries nothing). A scrub here also covers Google's own automatic
 * `page_view`, any future tag, and any token route added later.
 */

/**
 * Query parameters whose VALUE is a credential or a personal identifier.
 * The key is kept (so the shape of the funnel is still measurable) and the
 * value is replaced — dropping the key entirely would hide that a
 * token-bearing URL was visited at all.
 */
export const SENSITIVE_QUERY_PARAMS = [
  "token",
  "magic_token",
  "invite",
  "invitation",
  "invite_token",
  "access_token",
  "id_token",
  "refresh_token",
  "code",
  "pin",
  "otp",
  "secret",
  "key",
  "api_key",
  "password",
  "email",
] as const;

export const REDACTED = "[redacted]";

/**
 * Replace the value of every credential-bearing query parameter in `href`.
 *
 * Returns `href` unchanged when it holds none of them (the overwhelmingly
 * common case) and when it cannot be parsed — a scrubber must never be the
 * reason a page stops reporting.
 */
export function redactSensitiveQueryParams(href: string): string {
  let url: URL;
  try {
    url = new URL(href);
  } catch {
    return href;
  }

  let touched = false;
  for (const param of SENSITIVE_QUERY_PARAMS) {
    if (url.searchParams.has(param)) {
      url.searchParams.set(param, REDACTED);
      touched = true;
    }
  }

  // A token can also ride inside another parameter's value, which is how the
  // magic-link redirect leaked it a second time:
  // `?redirect=%2Fportal%2Fmagic%3Ftoken%3D<token>`. Redact any value that
  // embeds one of the sensitive keys as a nested query parameter.
  for (const [param, value] of Array.from(url.searchParams.entries())) {
    if (
      SENSITIVE_QUERY_PARAMS.some((p) => new RegExp(`[?&]${p}=`).test(value))
    ) {
      url.searchParams.set(param, REDACTED);
      touched = true;
    }
  }

  return touched ? url.href : href;
}

/**
 * The same redaction, as an inline `<head>` script, generated from the SAME
 * parameter list so the two copies cannot drift.
 *
 * It runs before `@next/third-parties`' gtag.js is loaded, so the
 * `gtag('set', …)` lands in `dataLayer` ahead of the `gtag('config', …)`
 * whose automatic `page_view` is the beacon that leaked. It only calls `set`
 * when the URL actually carries a credential: on every ordinary page GA keeps
 * its default behaviour untouched.
 */
export const analyticsUrlRedactScript = `(function(){try{var S=${JSON.stringify(
  SENSITIVE_QUERY_PARAMS,
)};var R=${JSON.stringify(REDACTED)};function scrub(h){if(!h)return h;var u;try{u=new URL(h);}catch(e){return h;}var t=false;S.forEach(function(p){if(u.searchParams.has(p)){u.searchParams.set(p,R);t=true;}});u.searchParams.forEach(function(v,k){for(var i=0;i<S.length;i++){if(new RegExp('[?&]'+S[i]+'=').test(v)){u.searchParams.set(k,R);t=true;break;}}});return t?u.href:h;}var loc=window.location.href;var ref=document.referrer;var sl=scrub(loc);var sr=scrub(ref);if(sl!==loc||sr!==ref){window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('set',{page_location:sl,page_referrer:sr});}}catch(e){}})();`;

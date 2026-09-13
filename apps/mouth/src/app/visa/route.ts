import { NextResponse } from "next/server";

/**
 * RETIRED DOOR — the public visa door is the Oracle.
 *
 * RULING Zero 2026-08-25: «Due porte: 301 → `/visa-oracle` subito» — the legacy
 * free-text funnel retires, and the funnel that carries the signed RulePack is
 * the one a visitor reaches. This path used to be a branch selector over the
 * legacy quiz; the quiz body is deleted rather than shadowed.
 *
 * WHY A ROUTE HANDLER AND NOT `permanentRedirect()` IN A PAGE — measured, not
 * assumed. A page whose body is `permanentRedirect("/visa-oracle")` is STATICALLY
 * PRERENDERED by Next 16: `next build` emits a 41KB HTML document for it
 * (`prerender-manifest.json`: `compute: "static"`, `response: "complete"`), and
 * `next start` then answers `HTTP/1.1 200 OK` with `x-nextjs-prerender: 1` and NO
 * `location:` header — the redirect only fires client-side after hydration, which
 * is worth nothing to a search engine and does not satisfy a 301 ruling. A route
 * handler cannot be prerendered into a document: it returns a Response, and this
 * one returns 308 — the same permanence and link equity as 301, and it preserves
 * the request method.
 *
 * WHY NOT `next.config.ts` redirects() — that table is shared by every funnel on
 * the domain (60+ ordering-sensitive entries for blog, kbli, tax, property and
 * second-home, including `:slug*` catch-alls), so a mistake there is site-wide;
 * here the blast radius is this one URL. Keeping a file at this path also keeps
 * `sitemap.test.ts`'s route walk enumerating `/visa`, so its absence from the
 * sitemap stays a written decision instead of a silent disappearance.
 *
 * NOT changed here: `/visa-oracle` stays `noindex` (its layout.tsx). Lifting it
 * is gated on Zero ratifying the 2026-08-23 four-condition checklist plus the
 * T2-copy fix, and shipping a robots change without that written ruling is a fail.
 */
export const dynamic = "force-dynamic";

export function GET(request: Request) {
  return NextResponse.redirect(new URL("/visa-oracle", request.url), 308);
}

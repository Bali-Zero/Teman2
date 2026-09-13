import { NextResponse } from "next/server";

/**
 * RETIRED DOOR — the legacy 4-question free-text quiz.
 *
 * RULING Zero 2026-08-25: «Due porte: 301 → `/visa-oracle` subito». This wizard
 * asked nationality / purpose / duration / budget and promised a visa *and a
 * cost* in four answers; the Oracle answers from a signed, versioned RulePack
 * instead. The wizard body is deleted, not shadowed.
 *
 * `[hash]` is deliberately untouched: a result link already shared with a visitor
 * still resolves at `/visa/match/<hash>`. Only the entry point retires, and the
 * sibling `layout.tsx` stays because that child still needs it — a layout does
 * not wrap a route handler, so it never sees this file.
 *
 * See `../route.ts` for the measurement that rules out a page-level
 * `permanentRedirect()` here (it prerenders to a 200 HTML document) and for why
 * this is not an entry in the shared `next.config.ts` redirect table.
 */
export const dynamic = "force-dynamic";

export function GET(request: Request) {
  return NextResponse.redirect(new URL("/visa-oracle", request.url), 308);
}

import { permanentRedirect } from "next/navigation";

/**
 * RETIRED DOOR — the public visa door is the Oracle.
 *
 * RULING Zero 2026-08-25: «Due porte: 301 → `/visa-oracle` subito» — the legacy
 * free-text funnel retires, the funnel that carries the signed RulePack is the
 * one a visitor reaches. This page used to be a branch selector over the legacy
 * quiz; the quiz body is deleted rather than shadowed, so no reordering of a
 * shared redirect table can ever serve a 200 quiz here again.
 *
 * Route-level rather than `next.config.ts` (D1, window W-VO-C): that config's
 * `redirects()` is shared by every funnel on the domain — 60+ ordering-sensitive
 * entries for blog, kbli, tax, property and second-home — and a mistake there is
 * site-wide. Here the blast radius is this one URL. `permanentRedirect` is
 * already the in-app idiom (`(blog)/[category]/[slug]/page.tsx`); it answers 308,
 * which carries the same permanence and link equity as 301.
 *
 * NOT changed here: `/visa-oracle` stays `noindex` (layout.tsx). Lifting it is
 * gated on Zero's ratification of the 2026-08-23 four-condition checklist plus
 * the T2-copy fix, and shipping a robots change without that written ruling is
 * a fail by this window's own acceptance.
 */
export default function VisaEntryPage(): never {
  permanentRedirect("/visa-oracle");
}

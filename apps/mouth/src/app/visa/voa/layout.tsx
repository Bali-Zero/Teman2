import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isGarudaVoaPublicEnabled } from "./flag";
import "../../portal/r19-fonts.css";
import "./voa-r19.css";

/**
 * Ship-dark per docs/factory/ASSEMBLY-LINE.md stage 6: the funnel is real
 * (owner decision 5 ratified "Concept A — The Stamp") but stays behind
 * `GARUDA_PUBLIC_ENABLED` until go-live (product.yaml owner decision 0,
 * currently blocked on the parent /visa page's own claims — see that
 * decision's note).
 *
 * This is enforced HERE, server-side, not left to the client or to `noindex`
 * alone. `noindex`/`nofollow` below only ask search engines not to list the
 * page — anyone with the URL sees it rendered anyway, and the mandate's
 * words are "running in PRODUCTION behind the flag", not "hidden from
 * Google". `isGarudaVoaPublicEnabled()` (in `./flag.ts` — see that file for
 * why it does not live here) fails CLOSED: only the literal string "true"
 * (case-insensitively) opens the route — unset, empty, "false", or a typo
 * all 404, matching the tombstone this route replaced.
 *
 * `force-dynamic` matters as much as the check itself, and belongs HERE on
 * the layout — it is route-segment config Next only reads at this level:
 * without it Next can statically render this layout once at build time and
 * bake in whatever the flag read as then, so a later env-var flip would
 * need a fresh deploy to take effect — which defeats the point of a
 * runtime flag.
 *
 * Remove this gate only alongside the go-live flip, and only together with
 * removing the noindex metadata below — the two protect different audiences
 * (bots vs. anyone with the link) and neither substitutes for the other.
 */
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Visa on Arrival — Bali Zero",
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

/**
 * Ground: `operative-light` — owner decision 2026-09-21, "voglio principale
 * la versione day light e non la dark". This attribute is the ONLY place the
 * funnel's ground is chosen; `voa-r19.css` no longer names a theme in any of
 * its selectors (it is keyed on `[data-product="my"][data-garuda-voa="r19"]`,
 * see that file's specificity note), so flipping this line moves the whole
 * skin and nothing else needs re-keying. That was not true before: the skin
 * used to be keyed on `[data-theme="operative-dark"]`, and the DELIBERA fase
 * 2 (a) flip in the other direction had to rewrite all fifty of its selectors
 * in the same PR or the `[data-funnel]` override would have stopped matching
 * and `semantic.css`'s `--accent-funnel` would have fallen back to red on the
 * primary purchase CTA.
 *
 * What makes the daylight ground safe for TEXT, measured rather than assumed
 * (`voa-contrast.computed.guard.test.tsx` recomputes all of it from
 * globals.css on every run): on `[data-theme="operative-light"][data-product="my"]`
 * the accent the funnel paints text with — `--bz-accent`, at the clock's
 * handoff link and at "Ask us anything before you pay" — is copper #a44b36,
 * 5.26:1 on the #f7f4ee ground and 5.64:1 on the #fffcf7 card. Both clear AA.
 * The naive flip, which is the one worth naming because it was the plan
 * before the numbers came in, was to keep the DARK block's lifted copper
 * #c46a52 and merely change the ground: that measures 3.37:1 on daylight and
 * fails AA for body text. The light my-block already carried its own,
 * darker copper — the flip did not need a new colour, it needed the check
 * that says which copper is in force.
 *
 * `layout.test.tsx` pins `operative-light` here, and the contrast guard
 * DERIVES its palette from this element rather than naming one, so neither
 * can be left behind by the next flip.
 */
export default function GarudaVoaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!isGarudaVoaPublicEnabled()) {
    notFound();
  }
  return (
    <div data-theme="operative-light" data-product="my" data-garuda-voa="r19">
      {children}
    </div>
  );
}

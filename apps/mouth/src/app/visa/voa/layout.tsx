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
 * GARUDA VOA DELIBERA FASE 2 (a): ground flipped to `operative-dark` — the
 * anthracite `--bz-base` #121016 the design-A/refutation pass measured, not a
 * cosmetic swap. `voa-r19.css`'s 15 selectors are re-keyed to
 * `[data-theme="operative-dark"]` in the same PR (design-A-refutation.md
 * finding 1, BLOCKING): flipping this attribute alone without that file would
 * make its `[data-funnel]` override never match, letting
 * `semantic.css`'s `--accent-funnel` fall back to its red default on the
 * primary purchase CTA. `layout.test.tsx` pins `operative-dark` here for the
 * same reason.
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
    <div data-theme="operative-dark" data-product="my" data-garuda-voa="r19">
      {children}
    </div>
  );
}

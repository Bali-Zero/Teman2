import type { Metadata } from "next";
import { notFound } from "next/navigation";

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
 * Google". `isGarudaVoaPublicEnabled()` fails CLOSED: only the literal
 * string "true" (case-insensitively) opens the route — unset, empty,
 * "false", or a typo all 404, matching the tombstone this route replaced.
 * A bare truthiness check would get this backwards (`Boolean("false")` is
 * `true`), and an unset Vercel env var must never be the thing that opens a
 * funnel by accident.
 *
 * `force-dynamic` matters as much as the check itself: without it Next can
 * statically render this layout once at build time and bake in whatever the
 * flag read as then, so a later env-var flip would need a fresh deploy to
 * take effect — which defeats the point of a runtime flag.
 *
 * Remove this gate only alongside the go-live flip, and only together with
 * removing the noindex metadata below — the two protect different audiences
 * (bots vs. anyone with the link) and neither substitutes for the other.
 */
export const dynamic = "force-dynamic";

export function isGarudaVoaPublicEnabled(): boolean {
  return (
    (process.env.GARUDA_PUBLIC_ENABLED ?? "").trim().toLowerCase() === "true"
  );
}

export const metadata: Metadata = {
  title: "Visa on Arrival — Bali Zero",
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

export default function GarudaVoaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!isGarudaVoaPublicEnabled()) {
    notFound();
  }
  return children;
}

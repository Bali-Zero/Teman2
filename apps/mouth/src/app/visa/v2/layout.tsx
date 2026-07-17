import type { Metadata } from "next";

/**
 * Visa Oracle v2 — prototype route (Track C PR C1, foundation only).
 *
 * noindex/nofollow: this is a foundation prototype (design tokens + mock
 * interview model + Q0), not the live public funnel — see
 * docs/plans/2026-07-17-visa-oracle-v2/track-c-experience-spec.md.
 */
export const metadata: Metadata = {
  title: "Visa Oracle v2 — prototype",
  robots: { index: false, follow: false },
};

export default function VisaOracleV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

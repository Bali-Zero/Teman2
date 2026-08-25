import type { Metadata } from "next";

/**
 * Ship-dark per docs/factory/ASSEMBLY-LINE.md stage 6: the funnel is real
 * (owner decision 5 ratified "Concept A — The Stamp") but stays noindex until
 * the owner flips `GARUDA_PUBLIC_ENABLED` and go-live (product.yaml owner
 * decision 0, currently blocked on the parent /visa page's own claims — see
 * that decision's note). Remove this override only alongside that flip.
 */
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
  return children;
}

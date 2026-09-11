import type { Metadata } from "next";
import { FunnelFrame } from "@balizero/core";
import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";
import { PropertyEligibilityBody } from "@/components/funnel/PropertyEligibilityBody";

export const metadata: Metadata = {
  title: "Property Eligibility Check — Bali Zoning & Legal Structure",
};

export default function PropertyPage() {
  return (
    <FunnelFrame
      funnel="property"
      sessionId="SSR"
      trust={{
        rating: GOOGLE_RATING,
        reviewCount: GOOGLE_REVIEW_COUNT,
      }}
    >
      <header style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, margin: 0 }}>
          Property Eligibility Check
        </h1>
        <p
          style={{
            color: "var(--text-secondary)",
            margin: "var(--space-2) 0 0",
            maxWidth: "56ch",
          }}
        >
          Enter Bali property coordinates to receive zoning classification,
          eligible legal structure (Hak Pakai / HGB via PMA / leasehold 30yr),
          applicable taxes (PBB, BPHTB), and risk score.
        </p>
      </header>
      <PropertyEligibilityBody />
    </FunnelFrame>
  );
}

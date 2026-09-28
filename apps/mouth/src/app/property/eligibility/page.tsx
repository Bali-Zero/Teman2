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
        <p
          style={{
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.28em",
            color: "var(--r19-copper, var(--accent-funnel))",
            margin: "0 0 var(--space-2)",
          }}
        >
          Property Check
        </p>
        <h1
          style={{
            fontFamily: "var(--font-serif)",
            fontWeight: 500,
            fontSize: "2rem",
            letterSpacing: "-0.01em",
            margin: 0,
          }}
        >
          Property Eligibility Check
        </h1>
        <p
          style={{
            color: "var(--text-secondary)",
            margin: "var(--space-2) 0 0",
            maxWidth: "56ch",
          }}
        >
          Enter Bali property coordinates and your buyer profile to receive
          zoning classification, whether your intended use is open to your buyer
          type, eligible legal structure, and applicable taxes.
        </p>
      </header>
      <PropertyEligibilityBody />
    </FunnelFrame>
  );
}

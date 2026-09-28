import type { Metadata } from "next";
import { FunnelFrame } from "@balizero/core";
import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";
import { PropertyEligibilityBody } from "@/components/funnel/PropertyEligibilityBody";
import styles from "./r19-funnel-frame.module.css";

export const metadata: Metadata = {
  title: "Property Eligibility Check — Bali Zoning & Buyer Eligibility",
};

export default function PropertyPage() {
  return (
    <div className={styles.scope}>
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
            Check a plot&rsquo;s zoning, what may be built there and what a
            buyer like you can do with it, then talk it through with us.
          </p>
        </header>
        <PropertyEligibilityBody />
      </FunnelFrame>
    </div>
  );
}

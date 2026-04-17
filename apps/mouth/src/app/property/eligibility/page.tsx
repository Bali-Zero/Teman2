import { FunnelFrame } from "@balizero/core";
import { PropertyEligibilityBody } from "@/components/funnel/PropertyEligibilityBody";

export default function PropertyPage() {
  return (
    <FunnelFrame
      funnel="property"
      sessionId="SSR"
      trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
    >
      <header style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, margin: 0 }}>
          Property Eligibility
        </h1>
        <p
          style={{
            color: "var(--text-secondary)",
            margin: "var(--space-2) 0 0",
            maxWidth: "56ch",
          }}
        >
          Inserisci coordinate di un plot a Bali: riceverai struttura legale
          eligible (Hak Pakai / HGB via PMA / rental 30y), tassazione (PBB,
          BPHTB) e risk score (tsunami, flood, saturation, erosion).
        </p>
      </header>
      <PropertyEligibilityBody />
    </FunnelFrame>
  );
}

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
          Idoneità Immobile
        </h1>
        <p
          style={{
            color: "var(--text-secondary)",
            margin: "var(--space-2) 0 0",
            maxWidth: "56ch",
          }}
        >
          Inserisci le coordinate di un lotto a Bali: riceverai struttura legale
          idonea (Hak Pakai / HGB via PMA / affitto 30 anni), tassazione (PBB,
          BPHTB) e punteggio di rischio (tsunami, alluvioni, saturazione,
          erosione).
        </p>
      </header>
      <PropertyEligibilityBody />
    </FunnelFrame>
  );
}

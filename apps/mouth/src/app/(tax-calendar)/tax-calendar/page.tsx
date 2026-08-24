import { FunnelFrame } from "@balizero/core";
import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";
import { TaxCalendarBody } from "@/components/funnel/TaxCalendarBody";
import { TAX_DEADLINES, getRegencies } from "@/app/api/tax-calendar/deadlines";

export default function TaxCalendarPage() {
  const deadlines = TAX_DEADLINES;
  const regencies = getRegencies();
  return (
    <FunnelFrame
      funnel="tax"
      sessionId="SSR"
      trust={{
        rating: GOOGLE_RATING,
        reviewCount: GOOGLE_REVIEW_COUNT,
      }}
    >
      <header style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, margin: 0 }}>
          Tax Compliance Calendar
        </h1>
        <p
          style={{
            color: "var(--text-secondary)",
            margin: "var(--space-2) 0 0",
          }}
        >
          Deadlines, reminders and compliance for businesses in Bali.
        </p>
      </header>
      <TaxCalendarBody deadlines={deadlines} regencies={regencies} />
    </FunnelFrame>
  );
}

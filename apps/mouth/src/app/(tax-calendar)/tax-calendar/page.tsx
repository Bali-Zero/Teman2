import { FunnelFrame } from "@balizero/core";
import { TaxCalendarBody } from "@/components/funnel/TaxCalendarBody";
import { TAX_DEADLINES, getRegencies } from "@/app/api/tax-calendar/deadlines";

export default function TaxCalendarPage() {
  const deadlines = TAX_DEADLINES;
  const regencies = getRegencies();
  return (
    <FunnelFrame
      funnel="tax"
      sessionId="SSR"
      trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
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

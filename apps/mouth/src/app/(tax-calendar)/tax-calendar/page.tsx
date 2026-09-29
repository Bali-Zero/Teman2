import { FunnelFrame } from "@balizero/core";
import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";
import { TaxCalendarBody } from "@/components/funnel/TaxCalendarBody";
import {
  getNextTaxDeadlines,
  getRegencies,
} from "@/app/api/tax-calendar/deadlines";
import styles from "./r19-funnel-frame.module.css";

// The deadlines are computed relative to request time, not build time: force
// per-request rendering so a date never goes stale between deploys.
export const dynamic = "force-dynamic";

export default function TaxCalendarPage() {
  const deadlines = getNextTaxDeadlines(new Date());
  const regencies = getRegencies();
  return (
    <div className={styles.scope}>
      <FunnelFrame
        funnel="tax"
        sessionId="SSR"
        trust={{
          rating: GOOGLE_RATING,
          reviewCount: GOOGLE_REVIEW_COUNT,
        }}
      >
        <header style={{ marginBottom: "var(--space-6)" }}>
          <h1
            style={{
              color: "var(--r19-ink)",
              fontFamily: "var(--font-serif)",
              fontSize: "2rem",
              fontWeight: 500,
              margin: 0,
            }}
          >
            Tax Compliance Calendar
          </h1>
          <p
            style={{
              color: "var(--r19-muted)",
              fontFamily: "var(--font-sans)",
              margin: "var(--space-2) 0 0",
            }}
          >
            Deadlines, reminders and compliance for businesses in Bali.
          </p>
        </header>
        <TaxCalendarBody deadlines={deadlines} regencies={regencies} />
      </FunnelFrame>
    </div>
  );
}

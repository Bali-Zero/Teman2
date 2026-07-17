import { FramingCard } from "@/components/visa-oracle/v2/FramingCard";

/**
 * Visa Oracle v2 — prototype route (Track C PR C1, foundation only).
 *
 * MOCK DATA ONLY. Demonstrates the vo2 design tokens (src/styles/visa-oracle-v2.css)
 * and the framing card + Q0 flow (src/lib/visa-oracle/v2/mock-tree.ts). No
 * API calls, no wiring to a backend — see
 * docs/plans/2026-07-17-visa-oracle-v2/track-c-experience-spec.md.
 */
export default function VisaOracleV2Page() {
  return (
    <main className="px-4 py-10 sm:px-6 lg:px-8">
      <FramingCard />
    </main>
  );
}

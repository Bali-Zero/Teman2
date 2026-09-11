import type { FC } from "react";

/**
 * Two columns: a star rating and a Google review count. Both are measured
 * and both carry a MEASURED_ON date at their source.
 *
 * A third column has been removed from this band twice, for two different
 * reasons. It first read `~15 min` — a response-time promise nobody had
 * measured (see apps/mouth/src/components/trust/response-time-claim.test.ts
 * for the measurement that retired it). It then read `5k+ clients`, whose
 * own source module records it as having no verified origin; standing next
 * to two dated numbers, the missing date became visible. Do not add a third
 * column unless the number carries a measurement date.
 *
 * `rating` and `reviewCount` are INJECTED, not imported. Their source of
 * truth is apps/mouth/src/lib/trust-figures.ts, and packages/core cannot
 * reach into an app: this package declares zero dependencies, has no tsconfig
 * of its own, and its vitest config carries no path alias — an `@/lib/...`
 * import here resolves in apps/mouth and fails under `cd packages/core &&
 * npx vitest --run`, which is an armed step of a required check. Pass them
 * from the call site; do not "fix" this into a cross-package import.
 */
export interface TrustBandProps {
  /** Star rating, verbatim from the measured source (e.g. "4.9"). */
  rating: string;
  /** Review count, verbatim from the measured source. */
  reviewCount: number;
}

export const TrustBand: FC<TrustBandProps> = ({ rating, reviewCount }) => (
  <section
    aria-label="Trust signals"
    style={{
      display: "grid",
      gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
      gap: "var(--space-4)",
      padding: "var(--space-6) var(--space-4)",
      background: "var(--surface-subtle)",
      borderTop: "1px solid var(--color-border-subtle)",
    }}
  >
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>★ {rating}</strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Rating</div>
    </div>
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        {reviewCount.toLocaleString("en-US")}
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Google reviews</div>
    </div>
  </section>
);

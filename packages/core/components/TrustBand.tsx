import type { FC } from "react";

/**
 * The third column used to read `~15 min` — a response-time promise nobody
 * had measured (see apps/mouth/src/components/trust/response-time-claim.test.ts
 * for the measurement that retired it). It now carries the Google review
 * count, which IS measured and carries a MEASURED_ON date.
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
  clientCount: number;
  /** Star rating, verbatim from the measured source (e.g. "4.9"). */
  rating: string;
  /** Review count, verbatim from the measured source. */
  reviewCount: number;
}

function formatK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}k+` : `${n}+`;
}

export const TrustBand: FC<TrustBandProps> = ({
  clientCount,
  rating,
  reviewCount,
}) => (
  <section
    aria-label="Trust signals"
    style={{
      display: "grid",
      gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
      gap: "var(--space-4)",
      padding: "var(--space-6) var(--space-4)",
      background: "var(--surface-subtle)",
      borderTop: "1px solid var(--color-border-subtle)",
    }}
  >
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        {formatK(clientCount)}
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Clients</div>
    </div>
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

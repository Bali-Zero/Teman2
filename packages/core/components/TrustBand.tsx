import type { FC } from "react";

export interface TrustBandProps {
  clientCount: number;
  rating: number;
  responseMinutes: number;
}

function formatK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}k+` : `${n}+`;
}

export const TrustBand: FC<TrustBandProps> = ({
  clientCount,
  rating,
  responseMinutes,
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
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        ★ {rating.toFixed(1)}
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Reviews</div>
    </div>
    <div>
      <strong style={{ fontSize: "var(--font-size-2xl)" }}>
        ~{responseMinutes} min
      </strong>
      <div style={{ color: "var(--color-text-secondary)" }}>Response</div>
    </div>
  </section>
);

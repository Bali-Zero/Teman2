"use client";

import type { FC } from "react";

export interface TrustNumber {
  value: string;
  label: string;
}

export interface AppTrustStripProps {
  items: [TrustNumber, TrustNumber, TrustNumber];
}

/** 3-number strip: concrete metrics only. X_BRAND_VOICE — never
 * "5k+ clients ★4.9"; prefer "5,021 visas filed since 2019". */
export const AppTrustStrip: FC<AppTrustStripProps> = ({ items }) => {
  return (
    <ul
      aria-label="Trust metrics"
      style={{
        listStyle: "none",
        margin: 0,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
        gap: "var(--space-3)",
        borderTop: "1px solid var(--color-border-subtle)",
        borderBottom: "1px solid var(--color-border-subtle)",
        padding: "var(--space-3) 0",
      }}
    >
      {items.map((it) => (
        <li key={it.label}>
          <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>
            {it.value}
          </div>
          <div
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-text-muted)",
            }}
          >
            {it.label}
          </div>
        </li>
      ))}
    </ul>
  );
};

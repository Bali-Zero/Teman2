"use client";

import type { FC, ReactNode } from "react";

export interface AppFrameProps {
  title: string;
  subtitle?: string;
  /** Mobile-first single column; 2-col desktop when sidebar provided. */
  sidebar?: ReactNode;
  /** Trust strip (3 numbers) shown above the main content. */
  trustStrip?: ReactNode;
  children: ReactNode;
  /** Optional coverage / result disclaimer under the content. */
  footer?: ReactNode;
}

/** Shared shell for all 4 homepage apps. Desktop ≥ 900px switches to
 * 2 columns (content | sidebar). Respects the Warm Depth tokens from
 * packages/core/styles/bz-tokens.css. */
export const AppFrame: FC<AppFrameProps> = ({
  title,
  subtitle,
  sidebar,
  trustStrip,
  children,
  footer,
}) => {
  return (
    <section
      aria-label={title}
      style={{
        maxWidth: "1120px",
        margin: "0 auto",
        padding: "var(--space-5) var(--space-4)",
        display: "grid",
        gap: "var(--space-5)",
      }}
    >
      <header style={{ display: "grid", gap: "var(--space-2)" }}>
        <h1 style={{ margin: 0, fontSize: "var(--text-2xl)", lineHeight: 1.2 }}>
          {title}
        </h1>
        {subtitle ? (
          <p
            style={{
              margin: 0,
              color: "var(--color-text-muted)",
              fontSize: "var(--text-md)",
            }}
          >
            {subtitle}
          </p>
        ) : null}
      </header>
      {trustStrip ? <div>{trustStrip}</div> : null}
      <div
        style={{
          display: "grid",
          gap: "var(--space-5)",
          gridTemplateColumns: sidebar ? "minmax(0, 1fr) 320px" : "1fr",
        }}
      >
        <main style={{ display: "grid", gap: "var(--space-4)" }}>
          {children}
        </main>
        {sidebar ? <aside>{sidebar}</aside> : null}
      </div>
      {footer ? (
        <footer
          style={{
            fontSize: "var(--text-sm)",
            color: "var(--color-text-muted)",
            borderTop: "1px solid var(--color-border-subtle)",
            paddingTop: "var(--space-4)",
          }}
        >
          {footer}
        </footer>
      ) : null}
    </section>
  );
};

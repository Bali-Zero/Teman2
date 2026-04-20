"use client";

import type { FC, ReactNode } from "react";

export interface AppFrameProps {
  title: string;
  subtitle?: string;
  /** Optional right-sidebar (desktop ≥900px). */
  sidebar?: ReactNode;
  /** 3-number trust strip (AppTrustStrip) rendered above the main content. */
  trustStrip?: ReactNode;
  children: ReactNode;
  /** Footer content (disclaimers, last-updated, etc.). */
  footer?: ReactNode;
  /**
   * When set, applies the data-funnel attribute on the root so
   * tokens like --accent-funnel resolve to the funnel hue (red/gold/cyan/green).
   */
  funnel?: "visa" | "kbli" | "tax" | "property";
}

export const AppFrame: FC<AppFrameProps> = ({
  title,
  subtitle,
  sidebar,
  trustStrip,
  children,
  footer,
  funnel,
}) => {
  return (
    <section
      role="region"
      aria-label={title}
      {...(funnel ? { "data-funnel": funnel } : {})}
      style={{
        maxWidth: "1120px",
        margin: "0 auto",
        padding: "var(--space-5, 2rem) var(--space-4, 1.5rem)",
        display: "grid",
        gap: "var(--space-5, 2rem)",
        minHeight: "100vh",
        background: "var(--surface-base)",
        color: "var(--text-primary, rgba(255, 255, 255, 0.96))",
      }}
    >
      <header style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}>
        <h1
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, 'Times New Roman', serif)",
            fontSize: "clamp(1.8rem, 5vw, 2.6rem)",
            lineHeight: 1.05,
            fontWeight: 400,
            letterSpacing: "-0.03em",
          }}
        >
          {title}
        </h1>
        {subtitle ? (
          <p
            style={{
              margin: 0,
              color: "var(--color-text-muted)",
              fontSize: "var(--text-md, 1rem)",
              lineHeight: 1.5,
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
          gap: "var(--space-5, 2rem)",
          gridTemplateColumns: sidebar ? "minmax(0, 1fr) 320px" : "1fr",
        }}
      >
        <main style={{ display: "grid", gap: "var(--space-4, 1.5rem)" }}>
          {children}
        </main>
        {sidebar ? <aside>{sidebar}</aside> : null}
      </div>
      {footer ? (
        <footer
          style={{
            fontSize: "var(--text-sm, 0.88rem)",
            color: "var(--color-text-muted)",
            borderTop: "1px solid var(--color-border-subtle)",
            paddingTop: "var(--space-4, 1.5rem)",
          }}
        >
          {footer}
        </footer>
      ) : null}
    </section>
  );
};

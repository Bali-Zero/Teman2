"use client";

import type { FC, ReactNode } from "react";

export interface AppFrameProps {
  title: string;
  subtitle?: string;
  /** Optional right-sidebar (desktop ≥900px). */
  sidebar?: ReactNode;
  /** Trust strip (AppTrustStrip) rendered above the main content. */
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
        // Explicit row sizing, not implicit `auto` for every row. Without
        // this, CSS Grid's default `align-content: normal` behaves as
        // `stretch` for auto row tracks: once real content is shorter than
        // the `minHeight: 100vh` below, ALL rows (header / trust strip /
        // main / footer) stretch equally to eat the leftover space. That
        // silently pushed every funnel's first interactive step below the
        // fold (measured on GARUDA VOA: ~260px of dead stretch at
        // 1280x900). Marking the main-content row `1fr` fixes it two ways
        // at once: header/trust-strip/footer size to content (no more dead
        // space above the fold), AND the main row itself absorbs the
        // leftover space instead of the browser spreading it around — so a
        // `footer` (disclaimers, CTA bar) still sits near the bottom of a
        // short page exactly as it did before, instead of floating right
        // under a now-compact header.
        gridTemplateRows: [
          "auto",
          trustStrip ? "auto" : null,
          "1fr",
          footer ? "auto" : null,
        ]
          .filter(Boolean)
          .join(" "),
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
          // This wrapper sits in the outer grid's `1fr` row, which absorbs
          // whatever height minHeight:100vh leaves over. Grid items stretch
          // to fill their row by default (align-items: stretch) — without
          // overriding it here, that leftover height would inflate this
          // wrapper's own box, and since it (and <main>, and AppWizard's own
          // internal grid below it) all default to `stretch` too, the extra
          // space cascades all the way down and reopens the same dead-space
          // bug one level deeper (visible as a large gap inside the wizard
          // body). `start` keeps this wrapper sized to its own content; the
          // outer row still grows to push a `footer` (if any) toward the
          // bottom of a short page.
          alignSelf: "start",
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

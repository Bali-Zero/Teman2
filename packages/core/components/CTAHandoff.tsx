"use client";
import type { CSSProperties, FC, MouseEventHandler } from "react";
import { buildWaDeeplink } from "../utils/wa-deeplink";

export interface CTAHandoffProps {
  source: string;
  sessionId: string;
  pdfHref?: string;
  onZantaraClick?: MouseEventHandler<HTMLButtonElement>;
  onWhatsAppClick?: MouseEventHandler<HTMLAnchorElement>;
  payload?: Record<string, unknown>;
}

/** WCAG 2.5.5 (Level AAA) minimum target size. The `.btn` classes on the
 *  three children are undefined in every stylesheet in this monorepo —
 *  measured 2026-09-02 on origin/main, `git grep "\.btn"` over *.css, *.ts
 *  and *.tsx returns zero — so the size has to live here. `inline-flex` is
 *  required alongside `minHeight`: an anchor is an inline box by default,
 *  and minimum height does not apply to non-replaced inline boxes. */
const tapTarget = {
  minHeight: 44,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
} as const;

/** The same undefined classes left the bar itself as the only visible
 *  "button": a full-width `--surface-base` slab (1,088 px on /kbli, measured
 *  2026-09-24) sticky over the content, holding an unstyled link. The rail
 *  now paints nothing and lets clicks through; only the actions are
 *  painted. The primary is outlined in the funnel accent rather than filled:
 *  it rides every viewport, so it must not out-shout the page's own primary
 *  action. */
const pill = {
  ...tapTarget,
  pointerEvents: "auto",
  padding: "0 var(--space-6)",
  borderRadius: 9999,
  fontSize: "0.875rem",
  fontWeight: 600,
  textDecoration: "none",
  whiteSpace: "nowrap",
  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)",
} as const satisfies CSSProperties;

const primary: CSSProperties = {
  ...pill,
  background: "var(--surface-base)",
  color: "var(--accent-funnel-text, var(--accent-funnel))",
  border: "1px solid var(--accent-funnel)",
};

const secondary: CSSProperties = {
  ...pill,
  background: "var(--surface-base)",
  color: "inherit",
  border: "1px solid var(--color-border-subtle)",
};

export const CTAHandoff: FC<CTAHandoffProps> = ({
  source,
  sessionId,
  pdfHref,
  onZantaraClick,
  onWhatsAppClick,
  payload,
}) => {
  const waUrl = buildWaDeeplink({ source, sessionId, payload });
  return (
    <div
      role="group"
      aria-label="Next actions"
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "flex-end",
        alignItems: "center",
        gap: "var(--space-3)",
        padding: "var(--space-3) var(--space-4)",
        position: "sticky",
        zIndex: 40,
        bottom: 0,
        pointerEvents: "none",
      }}
    >
      {pdfHref ? (
        <a href={pdfHref} className="btn btn-tertiary" style={secondary}>
          Scarica report
        </a>
      ) : null}
      {onZantaraClick ? (
        <button
          type="button"
          onClick={onZantaraClick}
          className="btn btn-secondary"
          style={secondary}
        >
          Chat with Zantara
        </button>
      ) : null}
      <a
        href={waUrl}
        onClick={onWhatsAppClick}
        className="btn btn-primary"
        target="_blank"
        rel="noreferrer"
        style={primary}
      >
        Talk on WhatsApp
      </a>
    </div>
  );
};

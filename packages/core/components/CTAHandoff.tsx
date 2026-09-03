"use client";
import type { FC, MouseEventHandler } from "react";
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
        alignItems: "center",
        gap: "var(--space-3)",
        padding: "var(--space-2) var(--space-4)",
        position: "sticky",
        zIndex: 40,
        bottom: 0,
        background: "var(--surface-base)",
        borderTop: "1px solid var(--color-border-subtle)",
      }}
    >
      {pdfHref ? (
        <a href={pdfHref} className="btn btn-tertiary" style={tapTarget}>
          Scarica report
        </a>
      ) : null}
      {onZantaraClick ? (
        <button
          type="button"
          onClick={onZantaraClick}
          className="btn btn-secondary"
          style={tapTarget}
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
        style={tapTarget}
      >
        Talk on WhatsApp
      </a>
    </div>
  );
};

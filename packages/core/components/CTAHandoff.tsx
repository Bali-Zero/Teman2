"use client";
import type { FC, MouseEventHandler } from "react";
import { buildWaDeeplink } from "../utils/wa-deeplink";

export interface CTAHandoffProps {
  source: string;
  sessionId: string;
  pdfHref?: string;
  onZantaraClick?: MouseEventHandler<HTMLButtonElement>;
  payload?: Record<string, unknown>;
}

export const CTAHandoff: FC<CTAHandoffProps> = ({
  source,
  sessionId,
  pdfHref,
  onZantaraClick,
  payload,
}) => {
  const waUrl = buildWaDeeplink({ source, sessionId, payload });
  return (
    <div
      role="group"
      aria-label="Next actions"
      style={{
        display: "flex",
        gap: "var(--space-3)",
        padding: "var(--space-4)",
        position: "sticky",
        bottom: 0,
        background: "var(--surface-base)",
        borderTop: "1px solid var(--color-border-subtle)",
      }}
    >
      {pdfHref ? (
        <a href={pdfHref} className="btn btn-tertiary">
          Scarica report
        </a>
      ) : null}
      {onZantaraClick ? (
        <button
          type="button"
          onClick={onZantaraClick}
          className="btn btn-secondary"
        >
          Chat with Zantara
        </button>
      ) : null}
      <a
        href={waUrl}
        className="btn btn-primary"
        target="_blank"
        rel="noreferrer"
      >
        Talk on WhatsApp
      </a>
    </div>
  );
};

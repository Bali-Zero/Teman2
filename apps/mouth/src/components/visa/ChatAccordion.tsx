"use client";

import { useState } from "react";
import { VisaChat } from "./VisaChat";

export interface ChatAccordionProps {
  checkHash: string;
  sessionJwt: string;
  daysRemaining?: number;
}

function deriveLabel(daysRemaining?: number): string {
  if (daysRemaining !== undefined) {
    if (daysRemaining <= 7) return "Urgent: ask questions before expiry";
    if (daysRemaining <= 30) return "2 weeks or less — ask 3 free questions";
  }
  return "Have doubts? Ask 3 free questions";
}

export function ChatAccordion({ checkHash, sessionJwt, daysRemaining }: ChatAccordionProps) {
  const [open, setOpen] = useState(false);

  if (!sessionJwt) return null;

  return (
    <section
      style={{
        marginTop: "var(--space-4, 1.5rem)",
        paddingTop: "var(--space-3, 1rem)",
        borderTop: "1px solid color-mix(in srgb, var(--color-text-muted) 20%, transparent)",
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          textAlign: "left",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--space-3, 1rem) var(--space-4, 1.5rem)",
          borderRadius: "0.5rem",
          background: "color-mix(in srgb, var(--color-text-muted) 6%, transparent)",
          color: "var(--color-text)",
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "1rem",
          border: "none",
          cursor: "pointer",
        }}
      >
        <span>{deriveLabel(daysRemaining)}</span>
        <span aria-hidden="true" style={{ fontSize: "1.25rem" }}>
          {open ? "−" : "+"}
        </span>
      </button>

      {open ? (
        <div style={{ marginTop: "var(--space-3, 1rem)" }}>
          <VisaChat checkHash={checkHash} sessionJwt={sessionJwt} />
        </div>
      ) : null}
    </section>
  );
}

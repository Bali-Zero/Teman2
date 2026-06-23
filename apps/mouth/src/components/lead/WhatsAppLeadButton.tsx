"use client";

import {
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
} from "react";

import { trackLeadWhatsAppCTA } from "@/lib/analytics";

/** Bare business wa.me link — no-JS href and fallback when capture fails.
 *  Same number used by the backend deeplink builder default. */
export const FALLBACK_WA_URL = "https://wa.me/6282210302328";

export interface WhatsAppLeadButtonProps {
  /** LeadSource wire value (backend enum): "article" | "kbli_navigator" | ... */
  source: string;
  /** Bullet rows rendered under "Context:" in the WhatsApp message. */
  whatsappContext: { label: string; value: string }[];
  /** Free-form payload for the lead_intents.context JSONB column. */
  context?: Record<string, unknown>;
  utm?: Record<string, unknown>;
  /** Shareable result reference (e.g. KBLI code → balizero.com/kbli/<code>). */
  resultHash?: string;
  fallbackHref?: string;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

/**
 * Tracked WhatsApp handoff: POST /api/lead/capture (writes a lead_intents
 * row, anonymous — no PII), then navigates to the returned pre-filled
 * wa.me deeplink. Any failure falls back to the bare wa.me link so the
 * user is never blocked by our own funnel.
 */
export function WhatsAppLeadButton({
  source,
  whatsappContext,
  context,
  utm,
  resultHash,
  fallbackHref = FALLBACK_WA_URL,
  className,
  style,
  children,
}: WhatsAppLeadButtonProps) {
  const [pending, setPending] = useState(false);

  const handoff = async (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    if (pending) return;
    setPending(true);
    try {
      const res = await fetch("/api/lead/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source,
          context: context ?? {},
          whatsapp_context: whatsappContext,
          result_hash: resultHash,
          utm,
        }),
      });
      if (!res.ok) throw new Error(`capture failed ${res.status}`);
      const json = (await res.json()) as {
        whatsapp_url: string;
        lead_intent_id?: string;
      };
      trackLeadWhatsAppCTA(source, {
        captured: true,
        lead_intent_id: json.lead_intent_id,
        result_ref: resultHash,
      });
      window.location.href = json.whatsapp_url;
    } catch {
      // Fallback handoff still counts as a CTA click — captured=false
      // distinguishes it (no lead_intents row was written).
      trackLeadWhatsAppCTA(source, { captured: false, result_ref: resultHash });
      window.location.href = fallbackHref;
    } finally {
      setPending(false);
    }
  };

  return (
    <a
      href={fallbackHref}
      onClick={handoff}
      className={className}
      style={style}
      aria-busy={pending}
      data-lead-source={source}
    >
      {children}
    </a>
  );
}

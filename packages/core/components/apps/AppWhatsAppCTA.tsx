"use client";

import { useState, type FC } from "react";

export interface AppWhatsAppCTAProps {
  /** Public app identifier: "visa_clock", "visa_match", etc. */
  source: string;
  /** Short headline above the button. */
  headline: string;
  /** 1-3 sentence explanation. Use X_BRAND_VOICE — no "we hope". */
  description: string;
  /** Context lines to prefill in the WA message body. */
  whatsappContext: { label: string; value: string }[];
  /** Optional shareable result hash (e.g. visa_checks.hash). */
  resultHash?: string;
  /** Free-form payload to persist in lead_intents.context. */
  context?: Record<string, unknown>;
  /** UTM overrides; the app usually fills these from the URL. */
  utm?: Record<string, unknown>;
  /** Override button label. */
  label?: string;
  /** Called after a successful lead capture with the intent id. */
  onCaptured?: (payload: { leadIntentId: string; whatsappUrl: string }) => void;
  /** API base; default empty string uses same-origin. */
  apiBase?: string;
}

/** Primary WhatsApp CTA. Calls POST /api/lead/capture, gets the wa.me
 * URL, and navigates the user to it. If the call fails, falls back to
 * a generic wa.me link so the user is never stuck. */
export const AppWhatsAppCTA: FC<AppWhatsAppCTAProps> = ({
  source,
  headline,
  description,
  whatsappContext,
  resultHash,
  context,
  utm,
  label = "Continue on WhatsApp",
  onCaptured,
  apiBase = "",
}) => {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handoff = async () => {
    setPending(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/lead/capture`, {
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
        lead_intent_id: string;
        whatsapp_url: string;
      };
      onCaptured?.({
        leadIntentId: json.lead_intent_id,
        whatsappUrl: json.whatsapp_url,
      });
      window.location.href = json.whatsapp_url;
    } catch {
      setError(
        "We could not open WhatsApp automatically. Opening the basic link.",
      );
      // Graceful fallback: a bare wa.me so the user is never stranded.
      window.location.href = "https://wa.me/628213107363";
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      style={{
        display: "grid",
        gap: "var(--space-3)",
        padding: "var(--space-4)",
        background: "var(--surface-raised)",
        borderRadius: 12,
        border: "1px solid var(--color-border-subtle)",
      }}
    >
      <strong style={{ fontSize: "var(--text-lg)" }}>{headline}</strong>
      <p
        style={{
          margin: 0,
          color: "var(--color-text-muted)",
          fontSize: "var(--text-md)",
          lineHeight: 1.5,
        }}
      >
        {description}
      </p>
      <button
        type="button"
        onClick={handoff}
        disabled={pending}
        style={{
          justifySelf: "start",
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: "var(--space-3) var(--space-5)",
          borderRadius: 8,
          border: "none",
          background: "#25D366",
          color: "#fff",
          fontWeight: 600,
          cursor: pending ? "wait" : "pointer",
          opacity: pending ? 0.7 : 1,
        }}
      >
        {pending ? "Opening…" : label}
      </button>
      {error ? (
        <p
          role="alert"
          style={{
            margin: 0,
            color: "var(--color-error)",
            fontSize: "var(--text-sm)",
          }}
        >
          {error}
        </p>
      ) : null}
    </div>
  );
};

"use client";

import { useEffect, useRef, useState, type FC } from "react";
import { useHaptic } from "../../hooks/useHaptic";

export interface AppWhatsAppCTAProps {
  source: string;
  headline: string;
  description: string;
  whatsappContext: { label: string; value: string }[];
  resultHash?: string;
  context?: Record<string, unknown>;
  utm?: Record<string, unknown>;
  /** Label shown above the stamp (before user scrolls past the key reveal). */
  defaultLabel?: string;
  /** Label shown after the user scrolls past the stampRef element. */
  postScrollLabel?: string;
  /**
   * Ref of the element which, once out of view (scrolled past), switches
   * the CTA to sticky-bottom + postScrollLabel.
   */
  stampRef?: React.RefObject<Element | null>;
  onCaptured?: (payload: { leadIntentId: string; whatsappUrl: string }) => void;
  apiBase?: string;
}

export const AppWhatsAppCTA: FC<AppWhatsAppCTAProps> = ({
  source,
  headline,
  description,
  whatsappContext,
  resultHash,
  context,
  utm,
  defaultLabel = "Continue on WhatsApp →",
  postScrollLabel,
  stampRef,
  onCaptured,
  apiBase = "",
}) => {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sticky, setSticky] = useState(false);
  const haptic = useHaptic();
  const selfRef = useRef<HTMLDivElement | null>(null);

  // Observe the stampRef — once it's out of view, pin sticky.
  useEffect(() => {
    if (!stampRef?.current) return;
    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      ([entry]) => setSticky(!entry.isIntersecting),
      { rootMargin: "-10% 0px 0px 0px", threshold: 0 },
    );
    io.observe(stampRef.current);
    return () => io.disconnect();
  }, [stampRef]);

  const handoff = async () => {
    haptic(10);
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
      setError("We could not open WhatsApp automatically. Opening the basic link.");
      window.location.href = "https://wa.me/628213107363";
    } finally {
      setPending(false);
    }
  };

  const label = sticky && postScrollLabel ? postScrollLabel : defaultLabel;

  return (
    <div
      ref={selfRef}
      style={{
        position: sticky ? "sticky" : "static",
        bottom: sticky ? "env(safe-area-inset-bottom, 0px)" : undefined,
        zIndex: sticky ? 50 : undefined,
        display: "grid",
        gap: "var(--space-3, 1rem)",
        padding: "var(--space-4, 1.5rem)",
        background: sticky
          ? "var(--surface-scrim, rgba(26, 50, 88, 0.92))"
          : "var(--surface-raised)",
        borderRadius: "12px",
        border: "1px solid var(--color-border-subtle)",
        boxShadow: sticky ? "0 -8px 24px rgba(0, 0, 0, 0.18)" : undefined,
        transition: "background var(--motion-duration-base, 250ms) var(--motion-curve-editorial), box-shadow var(--motion-duration-base, 250ms) var(--motion-curve-editorial)",
      }}
    >
      <strong style={{ fontSize: "var(--text-lg, 1.12rem)", color: "var(--text-primary)" }}>
        {headline}
      </strong>
      <p style={{
        margin: 0,
        color: "var(--color-text-muted)",
        fontSize: "var(--text-md, 1rem)",
        lineHeight: 1.5,
      }}>
        {description}
      </p>
      <button
        type="button"
        onClick={handoff}
        disabled={pending}
        style={{
          justifySelf: "start",
          padding: "var(--space-3, 0.85rem) var(--space-5, 1.5rem)",
          borderRadius: "4px",
          border: "none",
          background: "#25D366",
          color: "#fff",
          fontWeight: 600,
          cursor: pending ? "wait" : "pointer",
          opacity: pending ? 0.7 : 1,
          minHeight: "44px",
        }}
      >
        {pending ? "Opening…" : label}
      </button>
      {error ? (
        <p role="alert" style={{ margin: 0, color: "var(--color-error)", fontSize: "var(--text-sm, 0.88rem)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
};

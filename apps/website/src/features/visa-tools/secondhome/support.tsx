"use client";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { buildWhatsAppLink } from "../whatsapp";
/** The existing website adapter checks the PricingTool identity. No snapshot fallback. */
export function usePricingData(key: string | null, _category: string) {
  const [entry, setEntry] = useState<{ key: string; price: string } | null>(
    null,
  );
  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    fetch(`/api/service-price?key=${encodeURIComponent(key)}`, {
      signal: controller.signal,
      credentials: "omit",
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((result) => {
        if (
          !controller.signal.aborted &&
          result?.available === true &&
          typeof result.price === "string"
        )
          setEntry({ key, price: result.price });
      })
      .catch(() => {
        /* The guide omits an unavailable quote. */
      });
    return () => controller.abort();
  }, [key]);
  return { price: entry?.key === key ? entry.price : null };
}
export function ConsentBanner() {
  return (
    <aside className="visa-tool-note">
      Your Studio answers stay in this browser unless you copy a plan link or
      choose to share them. Anyone with that link can read the plan.{" "}
      <a href="/visa/privacy">How these tools handle data</a>
    </aside>
  );
}
/** User-operated deep link. Opening it does not create a CRM lead. */
export function WhatsAppLeadButton({
  whatsappContext,
  children,
  className,
  style,
}: {
  source: string;
  context?: Record<string, unknown>;
  utm?: Record<string, unknown>;
  whatsappContext: { label: string; value: string }[];
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  const message = [
    "Hi Bali Zero, I'd like to discuss my Second Home plan.",
    ...whatsappContext.slice(0, 6).map((row) => `${row.label}: ${row.value}`),
  ].join("\n");
  return (
    <a
      href={buildWhatsAppLink("visa", message)}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      style={style}
    >
      {children}
    </a>
  );
}

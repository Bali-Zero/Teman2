"use client";

import { trackVisaWhatsAppCTA } from "@/lib/analytics";

export function VisaHeaderWhatsApp() {
  return (
    <a
      href="https://wa.me/628213107363"
      onClick={() => trackVisaWhatsAppCTA("clicked", "header")}
      className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold"
      style={{ background: "var(--bz-accent)", color: "#fff" }}
    >
      WhatsApp
    </a>
  );
}

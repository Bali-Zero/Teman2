"use client";

import type { ReactNode } from "react";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";

/**
 * The home footer's WhatsApp link exactly as the pre-R19 v2 Footer rendered it
 * on "/": the home link with greeting and utm parameters, opened in a new tab,
 * firing home_whatsapp_cta with {trigger: "footer"}.
 */
export function FooterWhatsAppLink({ children }: { children: ReactNode }) {
  return (
    <a
      href={buildWhatsAppLink("home")}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() =>
        void trackFunnelEvent("home_whatsapp_cta", {
          sessionId: getOrCreateSessionId(),
          payload: { trigger: "footer" },
        })
      }
    >
      {children}
    </a>
  );
}

export const FUNNEL_EVENTS = [
  // --- Visa Oracle ---
  "visa_quiz_completed",
  "visa_result_viewed",
  "visa_chat_question",
  "visa_whatsapp_cta",
  "visa_calling_block",
  // Funnel home-block CTAs (4 per funnel × 4 funnels = 16)
  "visa_cta_click",
  "visa_consult_click",
  "visa_search_submit",
  "visa_suggestion_click",
  // --- KBLI Navigator ---
  "kbli_code_viewed",
  "kbli_search",
  "kbli_chat_question",
  "kbli_whatsapp_cta",
  "kbli_cta_click",
  "kbli_consult_click",
  "kbli_search_submit",
  "kbli_suggestion_click",
  // --- Tax Intelligence ---
  "tax_dashboard_viewed",
  "tax_whatsapp_cta",
  "tax_cta_click",
  "tax_consult_click",
  "tax_search_submit",
  "tax_suggestion_click",
  // --- Property Map ---
  "property_cta_clicked",
  "property_chat_question",
  "property_whatsapp_cta",
  "property_cta_click",
  "property_consult_click",
  "property_search_submit",
  "property_suggestion_click",
] as const;

export type FunnelEventName = (typeof FUNNEL_EVENTS)[number];

interface TrackArgs {
  sessionId: string;
  payload?: Record<string, unknown>;
}

declare global {
  // eslint-disable-next-line no-var
  var gtag: ((...args: unknown[]) => void) | undefined;
}

export async function trackFunnelEvent(
  name: FunnelEventName,
  args: TrackArgs,
): Promise<void> {
  const body = {
    session_id: args.sessionId,
    event: name,
    payload: args.payload ?? {},
  };
  if (typeof globalThis.gtag === "function") {
    globalThis.gtag("event", name, body);
  }
  try {
    await fetch("/api/analytics/funnel-event", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    /* silent — analytics never blocks UX */
  }
}

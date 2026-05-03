export const FUNNEL_EVENTS = [
  "visa_quiz_completed",
  "visa_result_viewed",
  "visa_chat_question",
  "visa_whatsapp_cta",
  "visa_calling_block",
  "kbli_code_viewed",
  "kbli_search",
  "kbli_chat_question",
  "kbli_whatsapp_cta",
  "tax_dashboard_viewed",
  "tax_whatsapp_cta",
  "property_cta_clicked",
  "property_chat_question",
  "property_whatsapp_cta",
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

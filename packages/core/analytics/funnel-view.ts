export const FUNNEL_EVENTS = [
  // --- Visa Oracle ---
  "visa_quiz_completed",
  "visa_result_viewed",
  "visa_chat_question",
  "visa_whatsapp_cta",
  "visa_calling_block",
  // --- Home CTAs ---
  "home_whatsapp_cta",
  // --- Lead Capture (WhatsAppLeadButton — articles + KBLI Navigator) ---
  // Unified cross-funnel WhatsApp handoff; payload: source = article|kbli_navigator|...
  "lead_whatsapp_cta",
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
  // NOTE (MYTHOS D5): "property_cta_clicked" is the single canonical property
  // CTA-click event (kept for GA4 continuity). The funnel home-block dispatcher
  // maps property + cta_click onto it — there is NO separate "property_cta_click".
  "property_cta_clicked",
  "property_chat_question",
  "property_whatsapp_cta",
  "property_consult_click",
  "property_search_submit",
  "property_suggestion_click",
  // --- Hero Section CTAs ---
  "hero_cta_book_call",
  "hero_cta_read_dispatch",
  // --- Persona doors (MYTHOS B2, IA-1; B2R2 adds tax) ---
  // Homepage "Start where you are." doors;
  // payload: door = visa|company|tax|property.
  "persona_door_click",
  // --- Booked Consultation (MYTHOS IA-3 scaffolding) ---
  // The /book consultation flow ships in B4; these events are allowlisted
  // ahead of it so measurement is ready on day one. NO emission sites yet —
  // the existing /book route is an editorial book reader, unrelated.
  "book_viewed",
  "book_form_started",
  "book_form_submitted",
  "book_call_confirmed",
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
  // MYTHOS D3/D9 foundation: capture the emitting hostname so the backend can
  // scope denominators to public hostnames (GA4 mixes 7 hostnames + localhost).
  // SSR-safe: omitted entirely outside the browser.
  const hostname =
    typeof window !== "undefined" ? window.location.hostname : undefined;
  const body = {
    session_id: args.sessionId,
    event: name,
    payload: args.payload ?? {},
    ...(hostname ? { hostname } : {}),
  };
  if (typeof globalThis.gtag === "function") {
    // GA4 cannot serialize nested objects — stringify payload so it arrives
    // as a readable string (e.g. '{"trigger":"nav"}') instead of [object Object].
    globalThis.gtag("event", name, {
      ...body,
      payload: JSON.stringify(body.payload),
    });
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

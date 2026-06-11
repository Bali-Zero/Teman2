/** Analytics events for homepage 4-app (visa, kbli, tax, zoning).
 *
 * Complements `funnel-view.ts` (legacy tracking for the decorative
 * FunnelFeature sections). The *app* events are emitted by the new
 * interactive apps and flow to the same `/api/analytics/funnel-event`
 * endpoint + GA4 gtag, so dashboards unify automatically.
 */

import { getOrCreateSessionId } from "../auth";

export type FunnelAppName =
  | "visa_clock"
  | "visa_match"
  | "kbli_decoder"
  | "kbli_builder"
  | "tax_gap"
  | "zoning_check";

/** Finite source-of-truth list of app_* event names (MYTHOS IA-8 app_*
 * reconciliation). The backend allowlist mirrors FUNNEL_EVENTS ∪ APP_EVENTS —
 * enforced by test_analytics_funnel_parity.py, which parses this const. */
export const APP_EVENTS = [
  "app_viewed",
  "app_branch_selected",
  "app_form_started",
  "app_form_submitted",
  "app_wizard_step_completed",
  "app_wizard_abandoned",
  "app_result_viewed",
  "app_cta_clicked",
  "app_whatsapp_handoff",
  "app_share_clicked",
  "app_pdf_downloaded",
  "app_email_subscribed",
] as const satisfies readonly string[];

export type AppEventType = (typeof APP_EVENTS)[number];

export type FunnelAppEvent =
  | { type: "app_viewed"; app: FunnelAppName }
  | { type: "app_branch_selected"; app: FunnelAppName; branch: string }
  | { type: "app_form_started"; app: FunnelAppName; field: string }
  | {
      type: "app_form_submitted";
      app: FunnelAppName;
      payload_keys: string[];
    }
  | {
      type: "app_wizard_step_completed";
      app: FunnelAppName;
      step: number;
      total: number;
    }
  | {
      type: "app_wizard_abandoned";
      app: FunnelAppName;
      last_step: number;
    }
  | {
      type: "app_result_viewed";
      app: FunnelAppName;
      result_hash: string;
    }
  | {
      type: "app_cta_clicked";
      app: FunnelAppName;
      cta_label: string;
      destination: string;
    }
  | {
      type: "app_whatsapp_handoff";
      app: FunnelAppName;
      lead_intent_id: string;
    }
  | {
      type: "app_share_clicked";
      app: FunnelAppName;
      channel: "copy" | "twitter" | "email";
    }
  | { type: "app_pdf_downloaded"; app: FunnelAppName }
  | {
      type: "app_email_subscribed";
      app: FunnelAppName;
      trigger_type: string;
    };

/** Compile-time parity proof: resolves to `true` only when APP_EVENTS exactly
 * covers FunnelAppEvent["type"] in BOTH directions. Adding a union variant
 * without listing it in APP_EVENTS (or vice versa) fails `tsc`. */
export type AppEventsExactlyCoverUnion =
  Exclude<FunnelAppEvent["type"], AppEventType> extends never
    ? Exclude<AppEventType, FunnelAppEvent["type"]> extends never
      ? true
      : never
    : never;
export const APP_EVENTS_COVER_UNION: AppEventsExactlyCoverUnion = true;

interface EmitOptions {
  /** Suppress network POST, keep only gtag (for dev / testing). */
  local?: boolean;
}

declare global {
  // eslint-disable-next-line no-var
  var gtag: ((...args: unknown[]) => void) | undefined;
}

const ENDPOINT = "/api/analytics/funnel-event";

/** Low-level emitter. Prefer `useFunnelApp(app)` in React. */
export async function emitFunnelAppEvent(
  event: FunnelAppEvent,
  opts: EmitOptions = {},
): Promise<void> {
  // GA4 — fire-and-forget.
  if (typeof globalThis.gtag === "function") {
    globalThis.gtag("event", event.type, event);
  }
  if (opts.local) return;
  // MYTHOS D3/D9 foundation: capture the emitting hostname (SSR-safe).
  const hostname =
    typeof window !== "undefined" ? window.location.hostname : undefined;
  try {
    await fetch(ENDPOINT, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      // session_id is REQUIRED by the backend FunnelEvent model (min 32
      // chars) — without it every app_* POST 422s and the "dashboards unify
      // automatically" promise in the module docstring was silently false.
      body: JSON.stringify({
        session_id: getOrCreateSessionId(),
        event: event.type,
        payload: event,
        ...(hostname ? { hostname } : {}),
      }),
      keepalive: true,
    });
  } catch {
    /* analytics never blocks UX */
  }
}

/** Simple factory — returns a typed helper bound to one app. Usable
 * from server and client components; the hook wrapper is in
 * `useFunnelApp.ts` for React-specific debouncing. */
export function createFunnelAppTracker(app: FunnelAppName) {
  return {
    viewed: () => emitFunnelAppEvent({ type: "app_viewed", app }),
    branchSelected: (branch: string) =>
      emitFunnelAppEvent({ type: "app_branch_selected", app, branch }),
    formStarted: (field: string) =>
      emitFunnelAppEvent({ type: "app_form_started", app, field }),
    formSubmitted: (payloadKeys: string[]) =>
      emitFunnelAppEvent({
        type: "app_form_submitted",
        app,
        payload_keys: payloadKeys,
      }),
    wizardStep: (step: number, total: number) =>
      emitFunnelAppEvent({
        type: "app_wizard_step_completed",
        app,
        step,
        total,
      }),
    wizardAbandoned: (lastStep: number) =>
      emitFunnelAppEvent({
        type: "app_wizard_abandoned",
        app,
        last_step: lastStep,
      }),
    resultViewed: (resultHash: string) =>
      emitFunnelAppEvent({
        type: "app_result_viewed",
        app,
        result_hash: resultHash,
      }),
    ctaClicked: (ctaLabel: string, destination: string) =>
      emitFunnelAppEvent({
        type: "app_cta_clicked",
        app,
        cta_label: ctaLabel,
        destination,
      }),
    whatsappHandoff: (leadIntentId: string) =>
      emitFunnelAppEvent({
        type: "app_whatsapp_handoff",
        app,
        lead_intent_id: leadIntentId,
      }),
    shareClicked: (channel: "copy" | "twitter" | "email") =>
      emitFunnelAppEvent({ type: "app_share_clicked", app, channel }),
    pdfDownloaded: () =>
      emitFunnelAppEvent({ type: "app_pdf_downloaded", app }),
    emailSubscribed: (triggerType: string) =>
      emitFunnelAppEvent({
        type: "app_email_subscribed",
        app,
        trigger_type: triggerType,
      }),
  };
}

export type FunnelAppTracker = ReturnType<typeof createFunnelAppTracker>;

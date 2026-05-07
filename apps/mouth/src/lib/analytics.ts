/**
 * Analytics utility for tracking CRM events
 * Sends events to the analytics service for monitoring usage patterns
 */

import type { AnalyticsProperties } from "./types/common";
import { logger } from "./logger";
import { toError } from "./types/common";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

export interface AnalyticsEvent {
  event_name: string;
  timestamp: string;
  user_id?: string;
  session_id?: string;
  properties: AnalyticsProperties;
}

let sessionId: string | null = null;

/**
 * Initialize analytics session
 */
export function initializeAnalytics(): void {
  if (typeof window !== "undefined" && !sessionId) {
    sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

/**
 * Track a user action/event
 */
export function trackEvent(
  eventName: string,
  properties?: AnalyticsProperties,
  userId?: string,
): void {
  if (typeof window === "undefined") return;

  initializeAnalytics();

  const event: AnalyticsEvent = {
    event_name: eventName,
    timestamp: new Date().toISOString(),
    user_id: userId,
    session_id: sessionId || undefined,
    properties: properties || {},
  };

  // Log to logger in development
  if (process.env.NODE_ENV === "development") {
    logger.debug("Analytics event", {
      component: "Analytics",
      action: "trackEvent",
      metadata: { eventName, userId },
    });
  }

  // Send to analytics endpoint if configured
  if (process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT) {
    sendAnalyticsEvent(event);
  }
}

/**
 * Track view mode changes
 */
export function trackViewModeChange(newMode: "kanban" | "list"): void {
  trackEvent("view_mode_changed", {
    view_mode: newMode,
    timestamp: Date.now(),
  });
}

/**
 * Track filter application
 */
export function trackFilterApplied(
  filterType: "status" | "type" | "assigned_to",
  filterValue: string,
): void {
  trackEvent("filter_applied", {
    filter_type: filterType,
    filter_value: filterValue,
    timestamp: Date.now(),
  });
}

/**
 * Track filter removal
 */
export function trackFilterRemoved(filterType: string): void {
  trackEvent("filter_removed", {
    filter_type: filterType,
    timestamp: Date.now(),
  });
}

/**
 * Track sort operation
 */
export function trackSortApplied(
  sortField: string,
  sortOrder: "asc" | "desc",
): void {
  trackEvent("sort_applied", {
    sort_field: sortField,
    sort_order: sortOrder,
    timestamp: Date.now(),
  });
}

/**
 * Track search operation
 */
export function trackSearch(query: string, resultsCount: number): void {
  trackEvent("search_performed", {
    query_length: query.length,
    results_count: resultsCount,
    timestamp: Date.now(),
  });
}

/**
 * Track case status change
 */
export function trackCaseStatusChanged(
  caseId: number,
  oldStatus: string,
  newStatus: string,
): void {
  trackEvent("case_status_changed", {
    case_id: caseId,
    old_status: oldStatus,
    new_status: newStatus,
    timestamp: Date.now(),
  });
}

/**
 * Track pagination
 */
export function trackPaginationChange(
  pageNumber: number,
  itemsPerPage: number,
): void {
  trackEvent("pagination_changed", {
    page_number: pageNumber,
    items_per_page: itemsPerPage,
    timestamp: Date.now(),
  });
}

/**
 * Send analytics event to backend (if endpoint is configured)
 */
async function sendAnalyticsEvent(event: AnalyticsEvent): Promise<void> {
  try {
    const endpoint = process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT;
    if (!endpoint) return;

    await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(event),
      keepalive: true, // Ensures request completes even if page unloads
    });
  } catch (error) {
    // Silently fail - don't interrupt user experience for analytics
    logger.warn(
      "Failed to send analytics event",
      { component: "Analytics", action: "sendAnalyticsEvent" },
      toError(error),
    );
  }
}

/**
 * Get current session ID
 */
export function getSessionId(): string | null {
  initializeAnalytics();
  return sessionId;
}

// ============================================================
// GA4 Custom Events — Conversion Funnel
// ============================================================

type GtagWindow = typeof window & { gtag?: (...args: unknown[]) => void };

/**
 * Send a custom event to GA4 via gtag.
 * No-op if gtag is not loaded (GA4 not configured).
 */
function sendGA4Event(
  eventName: string,
  params: Record<string, string | number | boolean>,
): void {
  if (typeof window === "undefined") return;
  const win = window as GtagWindow;
  if (typeof win.gtag !== "function") return;
  win.gtag("event", eventName, params);
}

/** Track when a new lead/client is created in CRM */
export function trackLeadCreated(source: string): void {
  sendGA4Event("lead_created", { event_category: "Conversion", source });
  trackEvent("lead_created", { source });
}

/** Track when a practice/case is started */
export function trackPracticeStarted(practiceType: string): void {
  sendGA4Event("practice_started", {
    event_category: "Conversion",
    practice_type: practiceType,
  });
  trackEvent("practice_started", { practice_type: practiceType });
}

/** Track when a document is uploaded */
export function trackDocumentUploaded(documentType: string): void {
  sendGA4Event("document_uploaded", {
    event_category: "Engagement",
    document_type: documentType,
  });
  trackEvent("document_uploaded", { document_type: documentType });
}

/** Track when a user logs into the portal */
export function trackPortalLogin(): void {
  sendGA4Event("portal_login", { event_category: "Engagement" });
  trackEvent("portal_login", {});
}

/** Track when a chat conversation starts */
export function trackChatStarted(channel: string): void {
  sendGA4Event("chat_started", {
    event_category: "Engagement",
    channel,
  });
  trackEvent("chat_started", { channel });
}

// ============================================================
// Client Tool Tracking — Visa Oracle, KBLI, Tax, Property
// ============================================================

// --- Visa Oracle ---

/** Track quiz completion with answers */
export function trackVisaQuizCompleted(answers: {
  nationality: string;
  purpose: string;
  duration: string;
  family: string;
}): void {
  sendGA4Event("visa_quiz_completed", {
    event_category: "VisaOracle",
    nationality: answers.nationality,
    purpose: answers.purpose,
    duration: answers.duration,
    family: answers.family,
  });
  trackEvent("visa_quiz_completed", answers);
  void trackFunnelEvent("visa_quiz_completed", {
    sessionId: getOrCreateSessionId(),
    payload: answers,
  });
}

/** Track visa recommendation result viewed */
export function trackVisaResultViewed(
  topVisa: string,
  visaCount: number,
): void {
  sendGA4Event("visa_result_viewed", {
    event_category: "VisaOracle",
    top_visa: topVisa,
    visa_count: visaCount,
  });
  trackEvent("visa_result_viewed", {
    top_visa: topVisa,
    visa_count: visaCount,
  });
  void trackFunnelEvent("visa_result_viewed", {
    sessionId: getOrCreateSessionId(),
    payload: { top_visa: topVisa, visa_count: visaCount },
  });
}

/** Track chat question sent in Visa Oracle */
export function trackVisaChatQuestion(remaining: number): void {
  sendGA4Event("visa_chat_question", {
    event_category: "VisaOracle",
    questions_remaining: remaining,
  });
  trackEvent("visa_chat_question", { questions_remaining: remaining });
  void trackFunnelEvent("visa_chat_question", {
    sessionId: getOrCreateSessionId(),
    payload: { questions_remaining: remaining },
  });
}

/** Track WhatsApp CTA shown or clicked */
export function trackVisaWhatsAppCTA(
  action: "shown" | "clicked",
  trigger: string,
): void {
  sendGA4Event("visa_whatsapp_cta", {
    event_category: "VisaOracle",
    action,
    trigger,
  });
  trackEvent("visa_whatsapp_cta", { action, trigger });
  void trackFunnelEvent("visa_whatsapp_cta", {
    sessionId: getOrCreateSessionId(),
    payload: { action, trigger },
  });
}

/** Track calling visa block shown */
export function trackVisaCallingBlock(nationality: string): void {
  sendGA4Event("visa_calling_block", {
    event_category: "VisaOracle",
    nationality,
  });
  trackEvent("visa_calling_block", { nationality });
  void trackFunnelEvent("visa_calling_block", {
    sessionId: getOrCreateSessionId(),
    payload: { nationality },
  });
}

// --- KBLI Navigator ---

/** Track KBLI code page viewed */
export function trackKBLICodeViewed(code: string, tier: string): void {
  sendGA4Event("kbli_code_viewed", {
    event_category: "KBLI",
    kbli_code: code,
    tier,
  });
  trackEvent("kbli_code_viewed", { kbli_code: code, tier });
  void trackFunnelEvent("kbli_code_viewed", {
    sessionId: getOrCreateSessionId(),
    payload: { kbli_code: code, tier },
  });
}

/** Track KBLI search performed */
export function trackKBLISearch(query: string, resultCount: number): void {
  sendGA4Event("kbli_search", {
    event_category: "KBLI",
    query_length: query.length,
    result_count: resultCount,
  });
  trackEvent("kbli_search", {
    query_length: query.length,
    result_count: resultCount,
  });
  void trackFunnelEvent("kbli_search", {
    sessionId: getOrCreateSessionId(),
    payload: { query_length: query.length, result_count: resultCount },
  });
}

/** Track ZantaraChat question on KBLI page */
export function trackKBLIChatQuestion(code: string): void {
  sendGA4Event("kbli_chat_question", {
    event_category: "KBLI",
    kbli_code: code,
  });
  trackEvent("kbli_chat_question", { kbli_code: code });
  void trackFunnelEvent("kbli_chat_question", {
    sessionId: getOrCreateSessionId(),
    payload: { kbli_code: code },
  });
}

// --- Tax ---

/** Track tax dashboard viewed */
export function trackTaxDashboardViewed(
  status: string,
  obligationCount: number,
): void {
  sendGA4Event("tax_dashboard_viewed", {
    event_category: "Tax",
    tax_status: status,
    obligation_count: obligationCount,
  });
  trackEvent("tax_dashboard_viewed", {
    tax_status: status,
    obligation_count: obligationCount,
  });
  void trackFunnelEvent("tax_dashboard_viewed", {
    sessionId: getOrCreateSessionId(),
    payload: { tax_status: status, obligation_count: obligationCount },
  });
}

// --- Property ---

/** Track property article-page CTA interaction (article slug + CTA type) */
export function trackPropertyArticleCTA(
  articleSlug: string,
  ctaType: string,
): void {
  sendGA4Event("property_cta_clicked", {
    event_category: "Property",
    article_slug: articleSlug,
    cta_type: ctaType,
  });
  trackEvent("property_cta_clicked", {
    article_slug: articleSlug,
    cta_type: ctaType,
  });
  void trackFunnelEvent("property_cta_clicked", {
    sessionId: getOrCreateSessionId(),
    payload: { article_slug: articleSlug, cta_type: ctaType },
  });
}

/** Track property analyze button clicked */
export function trackPropertyAnalyzeCTA(lat: number, lng: number): void {
  sendGA4Event("property_cta_clicked", {
    event_category: "Property",
    cta_type: "analyze",
    lat,
    lng,
  });
  trackEvent("property_cta_clicked", { cta_type: "analyze", lat, lng });
  void trackFunnelEvent("property_cta_clicked", {
    sessionId: getOrCreateSessionId(),
    payload: { cta_type: "analyze", lat, lng },
  });
}

/** Track AskZantara question on property article */
export function trackPropertyChatQuestion(articleSlug: string): void {
  sendGA4Event("property_chat_question", {
    event_category: "Property",
    article_slug: articleSlug,
  });
  trackEvent("property_chat_question", { article_slug: articleSlug });
  void trackFunnelEvent("property_chat_question", {
    sessionId: getOrCreateSessionId(),
    payload: { article_slug: articleSlug },
  });
}

/** Track property WA CTA click (placeholder for property_chat_question) */
export function trackPropertyWACTA(): void {
  sendGA4Event("property_chat_question", {
    event_category: "Property",
    cta_type: "whatsapp",
  });
  trackEvent("property_chat_question", { cta_type: "whatsapp" });
  void trackFunnelEvent("property_chat_question", {
    sessionId: getOrCreateSessionId(),
    payload: { cta_type: "whatsapp" },
  });
}

// ============================================================
// Funnel Home-Block CTA Helpers
// Dispatches to GA4 + internal CRM bus + funnel store.
// Used by FunnelFeature component for main CTA, consult/pricing
// CTA, search submit, and suggestion chip interactions.
// ============================================================

type FunnelCTAAction =
  | "cta_click"
  | "consult_click"
  | "search_submit"
  | "suggestion_click";

function _trackFunnelCTA(
  funnel: "visa" | "kbli" | "tax" | "property",
  action: FunnelCTAAction,
  extra?: Record<string, string | number | boolean>,
): void {
  // Event name: e.g. "visa_cta_click", "kbli_search_submit"
  const eventName = `${funnel}_${action}` as const;
  const params = { event_category: "FunnelCTA", funnel, ...extra };
  sendGA4Event(eventName, params);
  trackEvent(eventName, { funnel, ...extra });
  void trackFunnelEvent(
    // Cast is safe: all 16 combinations are in FUNNEL_EVENTS
    eventName as Parameters<typeof trackFunnelEvent>[0],
    { sessionId: getOrCreateSessionId(), payload: { funnel, ...extra } },
  );
}

/** Track Visa Oracle funnel block CTA interactions */
export function trackVisaCTA(
  action: FunnelCTAAction,
  extra?: Record<string, string | number | boolean>,
): void {
  _trackFunnelCTA("visa", action, extra);
}

/** Track KBLI Navigator funnel block CTA interactions */
export function trackKBLICTA(
  action: FunnelCTAAction,
  extra?: Record<string, string | number | boolean>,
): void {
  _trackFunnelCTA("kbli", action, extra);
}

/** Track Tax Intelligence funnel block CTA interactions */
export function trackTaxCTA(
  action: FunnelCTAAction,
  extra?: Record<string, string | number | boolean>,
): void {
  _trackFunnelCTA("tax", action, extra);
}

/** Track Property Map funnel home-block CTA interactions */
export function trackPropertyCTA(
  action: FunnelCTAAction,
  extra?: Record<string, string | number | boolean>,
): void {
  _trackFunnelCTA("property", action, extra);
}

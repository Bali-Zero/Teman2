/**
 * Analytics utility for tracking CRM events
 * Sends events to the analytics service for monitoring usage patterns
 */

import type { AnalyticsProperties } from './types/common';
import { logger } from './logger';
import { toError } from './types/common';

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
  if (typeof window !== 'undefined' && !sessionId) {
    sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

/**
 * Track a user action/event
 */
export function trackEvent(
  eventName: string,
  properties?: AnalyticsProperties,
  userId?: string
): void {
  if (typeof window === 'undefined') return;

  initializeAnalytics();

  const event: AnalyticsEvent = {
    event_name: eventName,
    timestamp: new Date().toISOString(),
    user_id: userId,
    session_id: sessionId || undefined,
    properties: properties || {},
  };

  // Log to logger in development
  if (process.env.NODE_ENV === 'development') {
    logger.debug('Analytics event', {
      component: 'Analytics',
      action: 'trackEvent',
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
export function trackViewModeChange(newMode: 'kanban' | 'list'): void {
  trackEvent('view_mode_changed', {
    view_mode: newMode,
    timestamp: Date.now(),
  });
}

/**
 * Track filter application
 */
export function trackFilterApplied(
  filterType: 'status' | 'type' | 'assigned_to',
  filterValue: string
): void {
  trackEvent('filter_applied', {
    filter_type: filterType,
    filter_value: filterValue,
    timestamp: Date.now(),
  });
}

/**
 * Track filter removal
 */
export function trackFilterRemoved(filterType: string): void {
  trackEvent('filter_removed', {
    filter_type: filterType,
    timestamp: Date.now(),
  });
}

/**
 * Track sort operation
 */
export function trackSortApplied(sortField: string, sortOrder: 'asc' | 'desc'): void {
  trackEvent('sort_applied', {
    sort_field: sortField,
    sort_order: sortOrder,
    timestamp: Date.now(),
  });
}

/**
 * Track search operation
 */
export function trackSearch(query: string, resultsCount: number): void {
  trackEvent('search_performed', {
    query_length: query.length,
    results_count: resultsCount,
    timestamp: Date.now(),
  });
}

/**
 * Track case status change
 */
export function trackCaseStatusChanged(caseId: number, oldStatus: string, newStatus: string): void {
  trackEvent('case_status_changed', {
    case_id: caseId,
    old_status: oldStatus,
    new_status: newStatus,
    timestamp: Date.now(),
  });
}

/**
 * Track pagination
 */
export function trackPaginationChange(pageNumber: number, itemsPerPage: number): void {
  trackEvent('pagination_changed', {
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
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(event),
      keepalive: true, // Ensures request completes even if page unloads
    });
  } catch (error) {
    // Silently fail - don't interrupt user experience for analytics
    logger.warn(
      'Failed to send analytics event',
      { component: 'Analytics', action: 'sendAnalyticsEvent' },
      toError(error)
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
function sendGA4Event(eventName: string, params: Record<string, string | number | boolean>): void {
  if (typeof window === 'undefined') return;
  const win = window as GtagWindow;
  if (typeof win.gtag !== 'function') return;
  win.gtag('event', eventName, params);
}

/** Track when a new lead/client is created in CRM */
export function trackLeadCreated(source: string): void {
  sendGA4Event('lead_created', { event_category: 'Conversion', source });
  trackEvent('lead_created', { source });
}

/** Track when a practice/case is started */
export function trackPracticeStarted(practiceType: string): void {
  sendGA4Event('practice_started', {
    event_category: 'Conversion',
    practice_type: practiceType,
  });
  trackEvent('practice_started', { practice_type: practiceType });
}

/** Track when a document is uploaded */
export function trackDocumentUploaded(documentType: string): void {
  sendGA4Event('document_uploaded', {
    event_category: 'Engagement',
    document_type: documentType,
  });
  trackEvent('document_uploaded', { document_type: documentType });
}

/** Track when a user logs into the portal */
export function trackPortalLogin(): void {
  sendGA4Event('portal_login', { event_category: 'Engagement' });
  trackEvent('portal_login', {});
}

/** Track when a chat conversation starts */
export function trackChatStarted(channel: string): void {
  sendGA4Event('chat_started', {
    event_category: 'Engagement',
    channel,
  });
  trackEvent('chat_started', { channel });
}

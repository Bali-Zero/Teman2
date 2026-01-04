/**
 * Analytics utility for tracking CRM events
 * Sends events to the analytics service for monitoring usage patterns
 */

export interface AnalyticsEvent {
  event_name: string;
  timestamp: string;
  user_id?: string;
  session_id?: string;
  properties: Record<string, any>;
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
  properties?: Record<string, any>,
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

  // Log to console in development
  if (process.env.NODE_ENV === 'development') {
    console.log('[Analytics]', event);
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
export function trackSortApplied(
  sortField: string,
  sortOrder: 'asc' | 'desc'
): void {
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
export function trackCaseStatusChanged(
  caseId: number,
  oldStatus: string,
  newStatus: string
): void {
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
    if (process.env.NODE_ENV === 'development') {
      console.warn('[Analytics] Failed to send event:', error);
    }
  }
}

/**
 * Get current session ID
 */
export function getSessionId(): string | null {
  initializeAnalytics();
  return sessionId;
}

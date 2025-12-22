/**
 * Monitoring utilities for production conversation tracking
 * Tracks long conversations and potential issues
 */

// Extend Window interface for global access
declare global {
  interface Window {
    conversationMonitor?: ConversationMonitor;
  }
}

export interface ConversationMetrics {
  turnCount: number;
  sessionId: string;
  startTime: Date;
  lastMessageTime: Date;
  errors: Array<{ type: string; message: string; timestamp: Date }>;
  timeouts: number;
  rateLimitHits: number;
}

class ConversationMonitor {
  private metrics: Map<string, ConversationMetrics> = new Map();
  private readonly MAX_TURNS_FOR_ALERT = 15;
  private readonly MAX_ERRORS_FOR_ALERT = 3;

  /**
   * Track a new message in a conversation
   */
  trackMessage(sessionId: string, isError: boolean = false, errorType?: string): void {
    const existing = this.metrics.get(sessionId) || {
      turnCount: 0,
      sessionId,
      startTime: new Date(),
      lastMessageTime: new Date(),
      errors: [],
      timeouts: 0,
      rateLimitHits: 0,
    };

    existing.turnCount++;
    existing.lastMessageTime = new Date();

    if (isError) {
      existing.errors.push({
        type: errorType || 'unknown',
        message: `Error at turn ${existing.turnCount}`,
        timestamp: new Date(),
      });

      if (errorType === 'TIMEOUT') {
        existing.timeouts++;
      } else if (errorType === 'QUOTA_EXCEEDED' || errorType === '429') {
        existing.rateLimitHits++;
      }
    }

    this.metrics.set(sessionId, existing);

    // Check for alerts
    this.checkAlerts(existing);
  }

  /**
   * Get metrics for a session
   */
  getMetrics(sessionId: string): ConversationMetrics | undefined {
    return this.metrics.get(sessionId);
  }

  /**
   * Clear metrics for a session (e.g., when conversation ends)
   */
  clearSession(sessionId: string): void {
    this.metrics.delete(sessionId);
  }

  /**
   * Check if alerts should be triggered
   */
  private checkAlerts(metrics: ConversationMetrics): void {
    // Alert for very long conversations
    if (metrics.turnCount >= this.MAX_TURNS_FOR_ALERT) {
      this.logAlert('LONG_CONVERSATION', {
        sessionId: metrics.sessionId,
        turnCount: metrics.turnCount,
        duration: Date.now() - metrics.startTime.getTime(),
      });
    }

    // Alert for multiple errors
    if (metrics.errors.length >= this.MAX_ERRORS_FOR_ALERT) {
      this.logAlert('MULTIPLE_ERRORS', {
        sessionId: metrics.sessionId,
        errorCount: metrics.errors.length,
        errors: metrics.errors,
      });
    }

    // Alert for multiple timeouts
    if (metrics.timeouts >= 2) {
      this.logAlert('MULTIPLE_TIMEOUTS', {
        sessionId: metrics.sessionId,
        timeoutCount: metrics.timeouts,
      });
    }

    // Alert for rate limit hits
    if (metrics.rateLimitHits >= 2) {
      this.logAlert('RATE_LIMIT_ISSUES', {
        sessionId: metrics.sessionId,
        rateLimitHits: metrics.rateLimitHits,
      });
    }
  }

  /**
   * Log alert (can be extended to send to monitoring service)
   */
  private logAlert(type: string, data: Record<string, unknown>): void {
    // Import dashboard dynamically to avoid circular dependency
    if (typeof window !== 'undefined') {
      import('./monitoring-dashboard').then(({ monitoringDashboard }) => {
        monitoringDashboard.recordAlert(type, data);
      });
    }
    if (typeof window !== 'undefined') {
      // Always log in browser (both dev and production)
      if (process.env.NODE_ENV === 'production') {
        // In production, send to monitoring service
        console.warn(`[MONITORING ALERT] ${type}:`, data);

        // Make monitor available globally for debugging
        if (
          !(window as unknown as { conversationMonitor?: ConversationMonitor }).conversationMonitor
        ) {
          (window as unknown as { conversationMonitor?: ConversationMonitor }).conversationMonitor =
            this;
        }

        // Could send to Sentry, DataDog, etc.
        // Example:
        // if ((window as unknown as { Sentry?: unknown }).Sentry) {
        //   (window as unknown as { Sentry: { captureMessage: (msg: string, opts: unknown) => void } }).Sentry.captureMessage(`Conversation Alert: ${type}`, {
        //     level: 'warning',
        //     extra: data,
        //   });
        // }
      } else {
        // In development, just log
        console.log(`[DEV MONITORING] ${type}:`, data);

        // Make monitor available globally for debugging
        if (
          !(window as unknown as { conversationMonitor?: ConversationMonitor }).conversationMonitor
        ) {
          (window as unknown as { conversationMonitor?: ConversationMonitor }).conversationMonitor =
            this;
        }
      }
    }
  }

  /**
   * Get all active sessions
   */
  getActiveSessions(): Array<ConversationMetrics> {
    return Array.from(this.metrics.values());
  }

  /**
   * Get summary statistics
   */
  getSummary(): {
    activeSessions: number;
    totalTurns: number;
    totalErrors: number;
    totalTimeouts: number;
    totalRateLimitHits: number;
  } {
    const sessions = Array.from(this.metrics.values());
    return {
      activeSessions: sessions.length,
      totalTurns: sessions.reduce((sum, s) => sum + s.turnCount, 0),
      totalErrors: sessions.reduce((sum, s) => sum + s.errors.length, 0),
      totalTimeouts: sessions.reduce((sum, s) => sum + s.timeouts, 0),
      totalRateLimitHits: sessions.reduce((sum, s) => sum + s.rateLimitHits, 0),
    };
  }
}

// Singleton instance
export const conversationMonitor = new ConversationMonitor();

/**
 * Hook to use conversation monitoring in React components
 */
export function useConversationMonitoring(sessionId: string | null) {
  if (typeof window === 'undefined') {
    return {
      trackMessage: () => {},
      trackError: () => {},
      clearSession: () => {},
    };
  }

  return {
    trackMessage: (isError: boolean = false, errorType?: string) => {
      if (sessionId) {
        conversationMonitor.trackMessage(sessionId, isError, errorType);
      }
    },
    trackError: (errorType: string) => {
      if (sessionId) {
        conversationMonitor.trackMessage(sessionId, true, errorType);
      }
    },
    clearSession: () => {
      if (sessionId) {
        conversationMonitor.clearSession(sessionId);
      }
    },
    getMetrics: () => {
      return sessionId ? conversationMonitor.getMetrics(sessionId) : undefined;
    },
  };
}

/**
 * Monitoring Dashboard - Visual interface for conversation metrics
 * Provides real-time monitoring and alerting capabilities
 */

import { conversationMonitor } from './monitoring';
import type { ConversationMetrics } from './monitoring';

export interface MonitoringDashboard {
  showSummary: () => void;
  showAlerts: () => void;
  showSessionDetails: (sessionId: string) => void;
  exportMetrics: () => string;
  clearOldSessions: (maxAgeMinutes?: number) => void;
}

class MonitoringDashboardImpl implements MonitoringDashboard {
  private alertHistory: Array<{ type: string; data: Record<string, unknown>; timestamp: Date }> =
    [];
  private readonly MAX_ALERT_HISTORY = 100;

  /**
   * Show summary of all metrics
   */
  showSummary(): void {
    const summary = conversationMonitor.getSummary();
    const activeSessions = conversationMonitor.getActiveSessions();

    console.group('📊 Conversation Monitoring Summary');
    console.log('Active Sessions:', summary.activeSessions);
    console.log('Total Turns:', summary.totalTurns);
    console.log('Total Errors:', summary.totalErrors);
    console.log('Total Timeouts:', summary.totalTimeouts);
    console.log('Total Rate Limit Hits:', summary.totalRateLimitHits);
    console.log('');

    if (activeSessions.length > 0) {
      console.group('Active Sessions Details');
      activeSessions.forEach((session) => {
        const duration = Date.now() - session.startTime.getTime();
        const durationMinutes = Math.floor(duration / 60000);
        console.log(`Session ${session.sessionId.substring(0, 8)}...`);
        console.log(`  Turns: ${session.turnCount}`);
        console.log(`  Duration: ${durationMinutes} minutes`);
        console.log(`  Errors: ${session.errors.length}`);
        console.log(`  Timeouts: ${session.timeouts}`);
        console.log(`  Rate Limits: ${session.rateLimitHits}`);
        console.log('');
      });
      console.groupEnd();
    }

    // Show recent alerts
    if (this.alertHistory.length > 0) {
      console.group('Recent Alerts');
      this.alertHistory.slice(-10).forEach((alert) => {
        const timeAgo = Math.floor((Date.now() - alert.timestamp.getTime()) / 1000);
        console.warn(`[${timeAgo}s ago] ${alert.type}:`, alert.data);
      });
      console.groupEnd();
    }

    console.groupEnd();
  }

  /**
   * Show all active alerts
   */
  showAlerts(): void {
    const activeSessions = conversationMonitor.getActiveSessions();
    const alerts: Array<{ type: string; sessionId: string; data: Record<string, unknown> }> = [];

    activeSessions.forEach((session) => {
      if (session.turnCount >= 15) {
        alerts.push({
          type: 'LONG_CONVERSATION',
          sessionId: session.sessionId,
          data: { turnCount: session.turnCount },
        });
      }
      if (session.errors.length >= 3) {
        alerts.push({
          type: 'MULTIPLE_ERRORS',
          sessionId: session.sessionId,
          data: { errorCount: session.errors.length },
        });
      }
      if (session.timeouts >= 2) {
        alerts.push({
          type: 'MULTIPLE_TIMEOUTS',
          sessionId: session.sessionId,
          data: { timeoutCount: session.timeouts },
        });
      }
      if (session.rateLimitHits >= 2) {
        alerts.push({
          type: 'RATE_LIMIT_ISSUES',
          sessionId: session.sessionId,
          data: { rateLimitHits: session.rateLimitHits },
        });
      }
    });

    if (alerts.length === 0) {
      console.log('✅ No active alerts');
      return;
    }

    console.group('⚠️ Active Alerts');
    alerts.forEach((alert) => {
      console.warn(`[${alert.type}] Session: ${alert.sessionId.substring(0, 8)}...`, alert.data);
    });
    console.groupEnd();
  }

  /**
   * Show detailed information about a specific session
   */
  showSessionDetails(sessionId: string): void {
    const metrics = conversationMonitor.getMetrics(sessionId);
    if (!metrics) {
      console.warn(`Session ${sessionId} not found`);
      return;
    }

    const duration = Date.now() - metrics.startTime.getTime();
    const durationMinutes = Math.floor(duration / 60000);
    const lastActivity = Date.now() - metrics.lastMessageTime.getTime();
    const lastActivitySeconds = Math.floor(lastActivity / 1000);

    console.group(`📋 Session Details: ${sessionId.substring(0, 16)}...`);
    console.log('Turn Count:', metrics.turnCount);
    console.log('Duration:', `${durationMinutes} minutes`);
    console.log('Last Activity:', `${lastActivitySeconds} seconds ago`);
    console.log('Errors:', metrics.errors.length);
    console.log('Timeouts:', metrics.timeouts);
    console.log('Rate Limit Hits:', metrics.rateLimitHits);
    console.log('');

    if (metrics.errors.length > 0) {
      console.group('Error History');
      metrics.errors.forEach((error, idx) => {
        const timeAgo = Math.floor((Date.now() - error.timestamp.getTime()) / 1000);
        console.error(`[${idx + 1}] [${timeAgo}s ago] ${error.type}:`, error.message);
      });
      console.groupEnd();
    }
    console.groupEnd();
  }

  /**
   * Export metrics as JSON string
   */
  exportMetrics(): string {
    const summary = conversationMonitor.getSummary();
    const activeSessions = conversationMonitor.getActiveSessions();
    const exportData = {
      timestamp: new Date().toISOString(),
      summary,
      sessions: activeSessions.map((session) => ({
        sessionId: session.sessionId,
        turnCount: session.turnCount,
        startTime: session.startTime.toISOString(),
        lastMessageTime: session.lastMessageTime.toISOString(),
        errors: session.errors.map((e) => ({
          type: e.type,
          message: e.message,
          timestamp: e.timestamp.toISOString(),
        })),
        timeouts: session.timeouts,
        rateLimitHits: session.rateLimitHits,
      })),
      alerts: this.alertHistory.map((alert) => ({
        type: alert.type,
        data: alert.data,
        timestamp: alert.timestamp.toISOString(),
      })),
    };

    return JSON.stringify(exportData, null, 2);
  }

  /**
   * Clear old sessions (older than maxAgeMinutes, default 60 minutes)
   */
  clearOldSessions(maxAgeMinutes: number = 60): void {
    const activeSessions = conversationMonitor.getActiveSessions();
    const now = Date.now();
    const maxAge = maxAgeMinutes * 60 * 1000;

    let cleared = 0;
    activeSessions.forEach((session) => {
      const age = now - session.lastMessageTime.getTime();
      if (age > maxAge) {
        conversationMonitor.clearSession(session.sessionId);
        cleared++;
      }
    });

    console.log(`🧹 Cleared ${cleared} old sessions (older than ${maxAgeMinutes} minutes)`);
  }

  /**
   * Record an alert (called by monitoring system)
   */
  recordAlert(type: string, data: Record<string, unknown>): void {
    this.alertHistory.push({
      type,
      data,
      timestamp: new Date(),
    });

    // Keep only last MAX_ALERT_HISTORY alerts
    if (this.alertHistory.length > this.MAX_ALERT_HISTORY) {
      this.alertHistory.shift();
    }
  }
}

// Singleton instance
export const monitoringDashboard = new MonitoringDashboardImpl();

// Make available globally for easy access
if (typeof window !== 'undefined') {
  (window as unknown as { monitoringDashboard?: MonitoringDashboardImpl }).monitoringDashboard =
    monitoringDashboard;
}

/**
 * Helper functions for easy console access
 */
export const monitoringHelpers = {
  /**
   * Quick summary command
   */
  summary: () => monitoringDashboard.showSummary(),

  /**
   * Quick alerts command
   */
  alerts: () => monitoringDashboard.showAlerts(),

  /**
   * Quick export command
   */
  export: () => {
    const json = monitoringDashboard.exportMetrics();
    console.log('📥 Metrics exported:');
    console.log(json);
    // Also copy to clipboard if possible
    if (navigator.clipboard) {
      navigator.clipboard.writeText(json).then(() => {
        console.log('✅ Metrics copied to clipboard');
      });
    }
  },

  /**
   * Quick clear old sessions command
   */
  clear: (minutes?: number) => monitoringDashboard.clearOldSessions(minutes),

  /**
   * Show help
   */
  help: () => {
    console.group('📚 Monitoring Dashboard Help');
    console.log('Available commands:');
    console.log('  monitoringHelpers.summary()  - Show summary of all metrics');
    console.log('  monitoringHelpers.alerts()   - Show active alerts');
    console.log('  monitoringHelpers.export()   - Export metrics as JSON');
    console.log('  monitoringHelpers.clear(60)   - Clear sessions older than 60 minutes');
    console.log('  monitoringHelpers.help()      - Show this help');
    console.log('');
    console.log('Or use:');
    console.log('  window.monitoringDashboard.showSummary()');
    console.log('  window.monitoringDashboard.showAlerts()');
    console.log('  window.conversationMonitor.getSummary()');
    console.groupEnd();
  },
};

// Make helpers available globally
if (typeof window !== 'undefined') {
  (window as unknown as { monitoringHelpers?: typeof monitoringHelpers }).monitoringHelpers =
    monitoringHelpers;
}

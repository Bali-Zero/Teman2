/**
 * Monitoring Dashboard - Visual interface for conversation metrics
 * Provides real-time monitoring and alerting capabilities
 */

import { logger } from "./logger";
import { toError } from "./types/common";
import type { Metadata } from "./types/common";
import { conversationMonitor } from "./monitoring";
import type { ConversationMetrics } from "./monitoring";

export interface MonitoringDashboard {
  showSummary: () => void;
  showAlerts: () => void;
  showSessionDetails: (sessionId: string) => void;
  exportMetrics: () => string;
  clearOldSessions: (maxAgeMinutes?: number) => void;
}

class MonitoringDashboardImpl implements MonitoringDashboard {
  private alertHistory: Array<{
    type: string;
    data: Record<string, unknown>;
    timestamp: Date;
  }> = [];
  private readonly MAX_ALERT_HISTORY = 100;

  /**
   * Show summary of all metrics
   */
  showSummary(): void {
    const summary = conversationMonitor.getSummary();
    const activeSessions = conversationMonitor.getActiveSessions();

    console.group("📊 Conversation Monitoring Summary");
    logger.debug(`Active Sessions: ${summary.activeSessions}`, {
      component: "Monitoring",
      action: "summary",
    });
    logger.debug(`Total Turns: ${summary.totalTurns}`, {
      component: "Monitoring",
      action: "summary",
    });
    logger.debug(`Total Errors: ${summary.totalErrors}`, {
      component: "Monitoring",
      action: "summary",
    });
    logger.debug(`Total Timeouts: ${summary.totalTimeouts}`, {
      component: "Monitoring",
      action: "summary",
    });
    logger.debug(`Total Rate Limit Hits: ${summary.totalRateLimitHits}`, {
      component: "Monitoring",
      action: "summary",
    });

    if (activeSessions.length > 0) {
      console.group("Active Sessions Details");
      activeSessions.forEach((session) => {
        const duration = Date.now() - session.startTime.getTime();
        const durationMinutes = Math.floor(duration / 60000);
        logger.debug(`Session ${session.sessionId.substring(0, 8)}...`, {
          component: "AUTO",
          action: "log",
        });
        logger.debug(`  Turns: ${session.turnCount}`, {
          component: "AUTO",
          action: "log",
        });
        logger.debug(`  Duration: ${durationMinutes} minutes`, {
          component: "AUTO",
          action: "log",
        });
        logger.debug(`  Errors: ${session.errors.length}`, {
          component: "AUTO",
          action: "log",
        });
        logger.debug(`  Timeouts: ${session.timeouts}`, {
          component: "AUTO",
          action: "log",
        });
        logger.debug(`  Rate Limits: ${session.rateLimitHits}`, {
          component: "AUTO",
          action: "log",
        });
        logger.debug("", { component: "AUTO", action: "log" });
      });
      console.groupEnd();
    }

    // Show recent alerts
    if (this.alertHistory.length > 0) {
      console.group("Recent Alerts");
      this.alertHistory.slice(-10).forEach((alert) => {
        const timeAgo = Math.floor(
          (Date.now() - alert.timestamp.getTime()) / 1000,
        );
        logger.warn(`[${timeAgo}s ago] ${alert.type}:`, {
          component: "AUTO",
          action: "warn",
          metadata: alert.data as Metadata,
        });
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
    const alerts: Array<{
      type: string;
      sessionId: string;
      data: Record<string, unknown>;
    }> = [];

    activeSessions.forEach((session) => {
      if (session.turnCount >= 15) {
        alerts.push({
          type: "LONG_CONVERSATION",
          sessionId: session.sessionId,
          data: { turnCount: session.turnCount },
        });
      }
      if (session.errors.length >= 3) {
        alerts.push({
          type: "MULTIPLE_ERRORS",
          sessionId: session.sessionId,
          data: { errorCount: session.errors.length },
        });
      }
      if (session.timeouts >= 2) {
        alerts.push({
          type: "MULTIPLE_TIMEOUTS",
          sessionId: session.sessionId,
          data: { timeoutCount: session.timeouts },
        });
      }
      if (session.rateLimitHits >= 2) {
        alerts.push({
          type: "RATE_LIMIT_ISSUES",
          sessionId: session.sessionId,
          data: { rateLimitHits: session.rateLimitHits },
        });
      }
    });

    if (alerts.length === 0) {
      logger.debug("✅ No active alerts", { component: "AUTO", action: "log" });
      return;
    }

    console.group("⚠️ Active Alerts");
    alerts.forEach((alert) => {
      logger.warn(
        `[${alert.type}] Session: ${alert.sessionId.substring(0, 8)}...`,
        {
          component: "AUTO",
          action: "warn",
          metadata: alert.data as Metadata,
        },
      );
    });
    console.groupEnd();
  }

  /**
   * Show detailed information about a specific session
   */
  showSessionDetails(sessionId: string): void {
    const metrics = conversationMonitor.getMetrics(sessionId);
    if (!metrics) {
      logger.warn(`Session ${sessionId} not found`, {
        component: "AUTO",
        action: "warn",
      });
      logger.warn(`Session ${sessionId} not found`, {
        component: "AUTO",
        action: "warn",
      });
      return;
    }

    const duration = Date.now() - metrics.startTime.getTime();
    const durationMinutes = Math.floor(duration / 60000);
    const lastActivity = Date.now() - metrics.lastMessageTime.getTime();
    const lastActivitySeconds = Math.floor(lastActivity / 1000);

    console.group(`📋 Session Details: ${sessionId.substring(0, 16)}...`);
    logger.debug(`Turn Count: ${metrics.turnCount}`, {
      component: "Monitoring",
      action: "sessionDetails",
    });
    logger.debug(`Duration: ${durationMinutes} minutes`, {
      component: "Monitoring",
      action: "sessionDetails",
    });
    logger.debug(`Last Activity: ${lastActivitySeconds} seconds ago`, {
      component: "Monitoring",
      action: "sessionDetails",
    });
    logger.debug(`Errors: ${metrics.errors.length}`, {
      component: "Monitoring",
      action: "sessionDetails",
    });
    logger.debug(`Timeouts: ${metrics.timeouts}`, {
      component: "Monitoring",
      action: "sessionDetails",
    });
    logger.debug(`Rate Limit Hits: ${metrics.rateLimitHits}`, {
      component: "Monitoring",
      action: "sessionDetails",
    });

    if (metrics.errors.length > 0) {
      console.group("Error History");
      metrics.errors.forEach((error, idx) => {
        const timeAgo = Math.floor(
          (Date.now() - error.timestamp.getTime()) / 1000,
        );
        logger.error(
          `[${idx + 1}] [${timeAgo}s ago] ${error.type}: ${error.message}`,
          { component: "AUTO", action: "error" },
          toError(
            `[${idx + 1}] [${timeAgo}s ago] ${error.type}: ${error.message}`,
          ),
        );
        logger.error(
          `[${idx + 1}] [${timeAgo}s ago] ${error.type}: ${error.message}`,
          {
            component: "AUTO",
            action: "error",
            metadata: { errorType: error.type, errorMessage: error.message },
          },
          toError(
            `[${idx + 1}] [${timeAgo}s ago] ${error.type}: ${error.message}`,
          ),
        );
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

    logger.debug(
      `🧹 Cleared ${cleared} old sessions (older than ${maxAgeMinutes} minutes)`,
      {
        component: "AUTO",
        action: "log",
      },
    );
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
if (typeof window !== "undefined") {
  (
    window as unknown as { monitoringDashboard?: MonitoringDashboardImpl }
  ).monitoringDashboard = monitoringDashboard;
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
    logger.debug("📥 Metrics exported:", { component: "AUTO", action: "log" });
    logger.debug(json, { component: "AUTO", action: "log" });
    // Also copy to clipboard if possible
    if (navigator.clipboard) {
      navigator.clipboard.writeText(json).then(() => {
        logger.debug("✅ Metrics copied to clipboard", {
          component: "AUTO",
          action: "log",
        });
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
    console.group("📚 Monitoring Dashboard Help");
    logger.debug("Available commands:", { component: "AUTO", action: "log" });
    logger.debug(
      '  monitoringHelpers.summary(, { component: "AUTO", action: "log" })  - Show summary of all metrics',
    );
    logger.debug(
      '  monitoringHelpers.alerts(, { component: "AUTO", action: "log" })   - Show active alerts',
    );
    logger.debug(
      '  monitoringHelpers.export(, { component: "AUTO", action: "log" })   - Export metrics as JSON',
    );
    logger.debug(
      '  monitoringHelpers.clear(60, { component: "AUTO", action: "log" })   - Clear sessions older than 60 minutes',
    );
    logger.debug(
      '  monitoringHelpers.help(, { component: "AUTO", action: "log" })      - Show this help',
    );
    logger.debug("", { component: "AUTO", action: "log" });
    logger.debug("Or use:", { component: "AUTO", action: "log" });
    logger.debug(
      '  window.monitoringDashboard.showSummary(, { component: "AUTO", action: "log" })',
    );
    logger.debug(
      '  window.monitoringDashboard.showAlerts(, { component: "AUTO", action: "log" })',
    );
    logger.debug(
      '  window.conversationMonitor.getSummary(, { component: "AUTO", action: "log" })',
    );
    console.groupEnd();
  },
};

// Make helpers available globally
if (typeof window !== "undefined") {
  (
    window as unknown as { monitoringHelpers?: typeof monitoringHelpers }
  ).monitoringHelpers = monitoringHelpers;
}

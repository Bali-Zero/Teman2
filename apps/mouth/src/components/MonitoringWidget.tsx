'use client';

import { useEffect, useState } from 'react';
import { conversationMonitor } from '@/lib/monitoring';
import { monitoringDashboard } from '@/lib/monitoring-dashboard';

interface MonitoringStats {
  activeSessions: number;
  totalTurns: number;
  totalErrors: number;
  totalTimeouts: number;
  totalRateLimitHits: number;
}

/**
 * Monitoring Widget - Visual component for monitoring dashboard
 * Shows real-time metrics and alerts
 */
export function MonitoringWidget() {
  const [stats, setStats] = useState<MonitoringStats | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [alerts, setAlerts] = useState<Array<{ type: string; count: number }>>([]);

  const buildAlerts = (activeSessions: ReturnType<typeof conversationMonitor.getActiveSessions>) => {
    const alertCounts: Record<string, number> = {};

    activeSessions.forEach((session) => {
      if (session.turnCount >= 15) {
        alertCounts['LONG_CONVERSATION'] = (alertCounts['LONG_CONVERSATION'] || 0) + 1;
      }
      if (session.errors.length >= 3) {
        alertCounts['MULTIPLE_ERRORS'] = (alertCounts['MULTIPLE_ERRORS'] || 0) + 1;
      }
      if (session.timeouts >= 2) {
        alertCounts['MULTIPLE_TIMEOUTS'] = (alertCounts['MULTIPLE_TIMEOUTS'] || 0) + 1;
      }
      if (session.rateLimitHits >= 2) {
        alertCounts['RATE_LIMIT_ISSUES'] = (alertCounts['RATE_LIMIT_ISSUES'] || 0) + 1;
      }
    });

    return Object.entries(alertCounts).map(([type, count]) => ({
      type,
      count,
    }));
  };

  useEffect(() => {
    // Only show in development or if explicitly enabled
    const showWidget = localStorage.getItem('showMonitoringWidget') === 'true';

    if (!showWidget) {
      return;
    }

    setIsVisible(true);
    const initialSummary = conversationMonitor.getSummary();
    setStats(initialSummary);
    const initialSessions = conversationMonitor.getActiveSessions();
    setAlerts(buildAlerts(initialSessions));

    // Update stats every 5 seconds
    const interval = setInterval(() => {
      const summary = conversationMonitor.getSummary();
      setStats(summary);

      // Check for alerts
      const activeSessions = conversationMonitor.getActiveSessions();
      setAlerts(buildAlerts(activeSessions));
    }, 5000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  if (!isVisible || !stats) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 bg-[var(--background-secondary)] border border-[var(--border)] rounded-lg p-4 shadow-lg z-50 max-w-sm">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-[var(--foreground)]">📊 Monitoring</h3>
        <button
          onClick={() => setIsVisible(false)}
          className="text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
          aria-label="Close monitoring widget"
        >
          ×
        </button>
      </div>

      <div className="space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-[var(--foreground-muted)]">Active Sessions:</span>
          <span className="text-[var(--foreground)] font-medium">{stats.activeSessions}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--foreground-muted)]">Total Turns:</span>
          <span className="text-[var(--foreground)] font-medium">{stats.totalTurns}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--foreground-muted)]">Errors:</span>
          <span
            className={`font-medium ${
              stats.totalErrors > 0 ? 'text-[var(--error)]' : 'text-[var(--foreground)]'
            }`}
          >
            {stats.totalErrors}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--foreground-muted)]">Timeouts:</span>
          <span
            className={`font-medium ${
              stats.totalTimeouts > 0 ? 'text-yellow-500' : 'text-[var(--foreground)]'
            }`}
          >
            {stats.totalTimeouts}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--foreground-muted)]">Rate Limits:</span>
          <span
            className={`font-medium ${
              stats.totalRateLimitHits > 0 ? 'text-orange-500' : 'text-[var(--foreground)]'
            }`}
          >
            {stats.totalRateLimitHits}
          </span>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <div className="text-xs font-semibold text-[var(--foreground-muted)] mb-1">
            ⚠️ Active Alerts:
          </div>
          {alerts.map((alert) => (
            <div key={alert.type} className="text-xs text-yellow-500">
              {alert.type}: {alert.count}
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-[var(--border)]">
        <button
          onClick={() => {
            monitoringDashboard.showSummary();
          }}
          className="text-xs text-[var(--accent)] hover:underline"
        >
          View Details in Console →
        </button>
      </div>
    </div>
  );
}

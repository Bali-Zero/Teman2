/**
 * Compliance Deadline Calendar Widget
 * Shows compliance deadlines with severity-based alerts
 */

'use client';

import { useState, useEffect, useMemo } from 'react';
import { Calendar as CalendarIcon, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import type {
  ComplianceItem,
  ComplianceAlert,
  AlertSeverity,
} from '@/lib/api/zantara-sdk/types';
import { ZantaraSDK } from '@/lib/api/zantara-sdk';

export interface ComplianceCalendarProps {
  clientId?: string;
  sdk: ZantaraSDK;
  daysAhead?: number;
  onAlertClick?: (alert: ComplianceAlert) => void;
}

const severityColors: Record<AlertSeverity, string> = {
  info: 'bg-blue-100 border-blue-300 text-blue-800',
  warning: 'bg-yellow-100 border-yellow-300 text-yellow-800',
  urgent: 'bg-orange-100 border-orange-300 text-orange-800',
  critical: 'bg-red-100 border-red-300 text-red-800',
};

const severityIcons: Record<AlertSeverity, typeof CalendarIcon> = {
  info: CalendarIcon,
  warning: Clock,
  urgent: AlertTriangle,
  critical: AlertTriangle,
};

export function ComplianceCalendar({
  clientId,
  sdk,
  daysAhead = 90,
  onAlertClick,
}: ComplianceCalendarProps) {
  const [deadlines, setDeadlines] = useState<ComplianceItem[]>([]);
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);

  useEffect(() => {
    loadComplianceData();
  }, [clientId, daysAhead]);

  const loadComplianceData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [deadlinesData, alertsData] = await Promise.all([
        sdk.getComplianceDeadlines({ client_id: clientId, days_ahead: daysAhead }),
        sdk.getComplianceAlerts(clientId),
      ]);
      setDeadlines(deadlinesData);
      setAlerts(alertsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load compliance data');
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (alertId: string) => {
    try {
      await sdk.acknowledgeAlert(alertId);
      await loadComplianceData();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  // Group alerts by date
  const alertsByDate = useMemo(() => {
    const grouped: Record<string, ComplianceAlert[]> = {};
    alerts.forEach((alert) => {
      const dateKey = new Date(alert.deadline).toDateString();
      if (!grouped[dateKey]) {
        grouped[dateKey] = [];
      }
      grouped[dateKey].push(alert);
    });
    return grouped;
  }, [alerts]);

  // Get upcoming deadlines sorted by date
  const upcomingDeadlines = useMemo(() => {
    return [...deadlines].sort(
      (a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
    );
  }, [deadlines]);

  // Calculate days until deadline
  const getDaysUntil = (deadline: string) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const deadlineDate = new Date(deadline);
    deadlineDate.setHours(0, 0, 0, 0);
    const diffTime = deadlineDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-muted-foreground">Loading compliance data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-destructive">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <CalendarIcon className="h-6 w-6" />
          Compliance Calendar
        </h2>
        <span className="text-sm text-muted-foreground">
          {alerts.length} active alert{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(['critical', 'urgent', 'warning', 'info'] as AlertSeverity[]).map((severity) => {
          const count = alerts.filter((a) => a.severity === severity && a.status === 'active')
            .length;
          const Icon = severityIcons[severity];
          return (
            <div
              key={severity}
              className={`p-4 border rounded-lg ${severityColors[severity]}`}
            >
              <div className="flex items-center gap-2">
                <Icon className="h-5 w-5" />
                <span className="text-sm font-medium capitalize">{severity}</span>
              </div>
              <div className="text-2xl font-bold mt-2">{count}</div>
            </div>
          );
        })}
      </div>

      {/* Upcoming Deadlines */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Upcoming Deadlines</h3>
        {upcomingDeadlines.length === 0 ? (
          <p className="text-sm text-muted-foreground italic text-center py-4">
            No upcoming deadlines
          </p>
        ) : (
          upcomingDeadlines.map((deadline) => {
            const daysUntil = getDaysUntil(deadline.deadline);
            const alert = alerts.find((a) => a.compliance_type === deadline.compliance_type);
            const severity = alert?.severity || 'info';
            const Icon = severityIcons[severity];

            return (
              <div
                key={deadline.item_id}
                className={`p-4 border rounded-lg ${
                  alert ? severityColors[severity] : 'bg-muted'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Icon className="h-5 w-5" />
                      <h4 className="font-medium">{deadline.title}</h4>
                    </div>
                    {deadline.description && (
                      <p className="text-sm mt-1">{deadline.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-xs">
                      <span>
                        Due: {new Date(deadline.deadline).toLocaleDateString()}
                      </span>
                      <span className="font-medium">
                        {daysUntil > 0
                          ? `${daysUntil} days remaining`
                          : daysUntil === 0
                          ? 'Due today'
                          : `${Math.abs(daysUntil)} days overdue`}
                      </span>
                    </div>
                    {deadline.required_documents.length > 0 && (
                      <div className="mt-2 text-xs">
                        <span className="font-medium">Required Documents: </span>
                        {deadline.required_documents.join(', ')}
                      </div>
                    )}
                    {deadline.estimated_cost && (
                      <div className="mt-1 text-xs">
                        <span className="font-medium">Estimated Cost: </span>
                        Rp {deadline.estimated_cost.toLocaleString('id-ID')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Active Alerts */}
      {alerts.filter((a) => a.status === 'active').length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold">Active Alerts</h3>
          {alerts
            .filter((a) => a.status === 'active')
            .sort((a, b) => {
              const severityOrder: Record<AlertSeverity, number> = {
                critical: 0,
                urgent: 1,
                warning: 2,
                info: 3,
              };
              return severityOrder[a.severity] - severityOrder[b.severity];
            })
            .map((alert) => {
              const Icon = severityIcons[alert.severity];
              return (
                <div
                  key={alert.alert_id}
                  className={`p-4 border rounded-lg cursor-pointer hover:opacity-90 transition-opacity ${severityColors[alert.severity]}`}
                  onClick={() => onAlertClick?.(alert)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <Icon className="h-5 w-5" />
                        <h4 className="font-medium">{alert.title}</h4>
                      </div>
                      <p className="text-sm mt-1">{alert.description}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs">
                        <span>
                          Deadline: {new Date(alert.deadline).toLocaleDateString()}
                        </span>
                        <span className="font-medium">
                          {alert.days_until > 0
                            ? `${alert.days_until} days remaining`
                            : alert.days_until === 0
                            ? 'Due today'
                            : `${Math.abs(alert.days_until)} days overdue`}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAcknowledge(alert.alert_id);
                      }}
                      className="px-3 py-1 text-xs bg-white border rounded hover:bg-gray-50"
                    >
                      Acknowledge
                    </button>
                  </div>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}








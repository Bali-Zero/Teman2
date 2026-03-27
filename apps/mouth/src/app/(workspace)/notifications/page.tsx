'use client';

import React, { useState, useEffect } from 'react';
import { Loader2, Mail, CheckCircle, XCircle, Clock, RefreshCw, Pause, Search, Bell } from 'lucide-react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/ui/toast';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface NotificationStats {
  total_alerts_24h: number;
  total_alerts_7d: number;
  total_alerts_30d: number;
  pending_count: number;
  sent_count_24h: number;
  failed_count_24h: number;
  alerts_by_type: Record<string, number>;
  alerts_by_status: Record<string, number>;
  top_clients: Array<{
    id: number;
    name: string;
    email: string;
    alert_count: number;
  }>;
}

interface Alert {
  id: number;
  client_id: number;
  client_name: string;
  client_email: string;
  alert_type: string;
  status: string;
  email_subject: string;
  created_at: string;
  sent_at: string | null;
  error_message: string | null;
}

export default function NotificationsDashboardPage() {
  const { success, error } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<NotificationStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [systemStatus, setSystemStatus] = useState<string>('unknown');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedAlert, setExpandedAlert] = useState<number | null>(null);

  const loadDashboard = async () => {
    try {
      setIsLoading(true);
      const data = await api.crm.request<{
        stats: typeof stats;
        recent_alerts: typeof alerts;
        system_status: typeof systemStatus;
      }>('/api/admin/notifications/dashboard');
      setStats(data.stats);
      setAlerts(data.recent_alerts);
      setSystemStatus(data.system_status);
    } catch (err) {
      error('Failed to load dashboard', 'Please try again');
      logger.error('Failed to load notifications dashboard', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRetryFailed = async () => {
    try {
      const result = await api.crm.request('/api/admin/notifications/retry', {
        method: 'POST',
        body: JSON.stringify({}),
      });
      success('Retry completed', (result as { message: string }).message);
      loadDashboard();
    } catch (err) {
      error('Retry failed', 'Please try again');
    }
  };

  const handlePauseClient = (clientId: number) => {
    toast('Pause notifications for this client for 24 hours?', {
      action: {
        label: 'Pause',
        onClick: async () => {
          try {
            await api.crm.request(`/api/admin/notifications/pause-client?client_id=${clientId}`, {
              method: 'POST',
            });
            success('Client paused', 'Notifications paused for 24 hours');
            loadDashboard();
          } catch (err) {
            error('Failed to pause client', 'Please try again');
          }
        },
      },
      cancel: { label: 'Cancel', onClick: () => toast.dismiss() },
    });
  };

  const filteredAlerts = alerts.filter((alert) => {
    if (filterStatus && alert.status !== filterStatus) return false;
    if (filterType && alert.alert_type !== filterType) return false;
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        alert.client_name.toLowerCase().includes(query) ||
        alert.client_email.toLowerCase().includes(query) ||
        alert.email_subject.toLowerCase().includes(query)
      );
    }
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'sent':
        return 'text-green-600 bg-green-50';
      case 'pending':
        return 'text-amber-600 bg-amber-50';
      case 'failed':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'sent':
        return <CheckCircle className="w-4 h-4" />;
      case 'pending':
        return <Clock className="w-4 h-4" />;
      case 'failed':
        return <XCircle className="w-4 h-4" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notifications Dashboard</h1>
          <p className="text-muted-foreground">Monitor automated email alerts</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadDashboard} className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
          {stats?.failed_count_24h ? (
            <Button variant="destructive" size="sm" onClick={handleRetryFailed} className="gap-2">
              <RefreshCw className="w-4 h-4" />
              Retry Failed ({stats.failed_count_24h})
            </Button>
          ) : null}
        </div>
      </div>

      {/* System Status */}
      <div
        className={cn(
          'rounded-lg border p-4 flex items-center gap-3',
          systemStatus === 'healthy'
            ? 'border-green-200 bg-green-50'
            : systemStatus === 'degraded'
              ? 'border-red-200 bg-red-50'
              : 'border-amber-200 bg-amber-50'
        )}
      >
        <div
          className={cn(
            'w-3 h-3 rounded-full',
            systemStatus === 'healthy'
              ? 'bg-green-500'
              : systemStatus === 'degraded'
                ? 'bg-red-500'
                : 'bg-amber-500'
          )}
        />
        <div>
          <p className="font-medium">
            System Status: {systemStatus.charAt(0).toUpperCase() + systemStatus.slice(1)}
          </p>
          <p className="text-sm text-muted-foreground">
            {systemStatus === 'healthy'
              ? 'All systems operational'
              : systemStatus === 'degraded'
                ? 'Multiple failures detected - attention required'
                : 'Pending alerts backlog - processing'}
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="24h Alerts" value={stats.total_alerts_24h} icon={Mail} color="blue" />
          <StatCard title="Pending" value={stats.pending_count} icon={Clock} color="amber" />
          <StatCard
            title="Sent (24h)"
            value={stats.sent_count_24h}
            icon={CheckCircle}
            color="green"
          />
          <StatCard
            title="Failed (24h)"
            value={stats.failed_count_24h}
            icon={XCircle}
            color={stats.failed_count_24h > 0 ? 'red' : 'gray'}
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search clients..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-64"
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 rounded-md border bg-background"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-3 py-2 rounded-md border bg-background"
        >
          <option value="">All Types</option>
          <option value="passport_warning">Passport Warning</option>
          <option value="passport_critical">Passport Critical</option>
          <option value="visa_critical">Visa Critical</option>
          <option value="birthday">Birthday</option>
        </select>
      </div>

      {/* Alerts Table */}
      <div className="rounded-xl border">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">Client</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Type</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Subject</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Time</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-muted-foreground">
                    <Bell className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    {searchQuery || filterStatus || filterType
                      ? 'No notifications match your filters.'
                      : 'No notifications yet.'}
                  </td>
                </tr>
              )}
              {filteredAlerts.map((alert) => (
                <React.Fragment key={alert.id}>
                  <tr
                    className="border-t hover:bg-muted/50 cursor-pointer"
                    onClick={() => setExpandedAlert(expandedAlert === alert.id ? null : alert.id)}
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium">{alert.client_name}</p>
                        <p className="text-xs text-muted-foreground">{alert.client_email}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm capitalize">
                        {alert.alert_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                          getStatusColor(alert.status)
                        )}
                      >
                        {getStatusIcon(alert.status)}
                        {alert.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm truncate max-w-xs">{alert.email_subject}</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        <p className="text-sm text-muted-foreground">
                          {new Date(alert.created_at).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </p>
                        {(() => {
                          const ageDays = Math.floor(
                            (Date.now() - new Date(alert.created_at).getTime()) / 86400000
                          );
                          if (ageDays < 1) return null;
                          const label =
                            ageDays >= 365
                              ? `${Math.floor(ageDays / 365)}y ago`
                              : ageDays >= 30
                                ? `${Math.floor(ageDays / 30)}mo ago`
                                : ageDays >= 7
                                  ? `${Math.floor(ageDays / 7)}w ago`
                                  : `${ageDays}d ago`;
                          return (
                            <span
                              className="text-[10px] px-1.5 py-0.5 rounded tabular-nums self-start"
                              style={{
                                background: 'rgba(255,255,255,0.04)',
                                color: 'var(--muted-foreground)',
                              }}
                            >
                              {label}
                            </span>
                          );
                        })()}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePauseClient(alert.client_id);
                        }}
                      >
                        <Pause className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                  {expandedAlert === alert.id && (
                    <tr className="border-t bg-muted/30">
                      <td colSpan={6} className="px-4 py-4">
                        <div className="space-y-2">
                          <p className="text-sm font-medium">Email Subject:</p>
                          <p className="text-sm">{alert.email_subject}</p>
                          {alert.error_message && (
                            <>
                              <p className="text-sm font-medium text-red-600 mt-2">Error:</p>
                              <p className="text-sm text-red-600">{alert.error_message}</p>
                            </>
                          )}
                          {alert.sent_at && (
                            <p className="text-sm text-muted-foreground mt-2">
                              Sent:{' '}
                              {new Date(alert.sent_at).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })}{' '}
                              {new Date(alert.sent_at).toLocaleTimeString('en-US', {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top Clients */}
      {stats?.top_clients && stats.top_clients.length > 0 && (
        <div className="rounded-xl border p-6">
          <h3 className="font-semibold mb-4">Top Clients by Alert Volume (30 days)</h3>
          <div className="space-y-3">
            {stats.top_clients.slice(0, 5).map((client) => (
              <div
                key={client.id}
                className="flex items-center justify-between py-2 border-b last:border-0"
              >
                <div>
                  <p className="font-medium">{client.name}</p>
                  <p className="text-sm text-muted-foreground">{client.email}</p>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium">{client.alert_count} alerts</span>
                  <Button variant="ghost" size="sm" onClick={() => handlePauseClient(client.id)}>
                    <Pause className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: number;
  icon: React.ElementType;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-gray-50 text-gray-600',
  };

  return (
    <div className={cn('rounded-xl border p-4', colorClasses[color])}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-white/50">
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm opacity-80">{title}</p>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import {
  Users,
  Clock,
  Calendar,
  Download,
  ArrowLeft,
  Loader2,
  RefreshCw,
  Circle,
  TrendingUp,
} from 'lucide-react';

interface TeamMember {
  user_id: string;
  email: string;
  is_online: boolean;
  last_action: string;
  last_action_type: string;
}

interface DailyHours {
  user_id: string;
  email: string;
  date: string;
  clock_in: string;
  clock_out: string;
  hours_worked: number;
}

interface WeeklySummary {
  user_id: string;
  email: string;
  week_start: string;
  days_worked: number;
  total_hours: number;
  avg_hours_per_day: number;
}

type TabType = 'overview' | 'daily' | 'weekly';

export default function AdminPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [teamStatus, setTeamStatus] = useState<TeamMember[]>([]);
  const [dailyHours, setDailyHours] = useState<DailyHours[]>([]);
  const [weeklySummary, setWeeklySummary] = useState<WeeklySummary[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);

  const loadTeamStatus = useCallback(async () => {
    try {
      const status = await api.getTeamStatus();
      setTeamStatus(status);
    } catch (err) {
      console.error('Failed to load team status:', err);
    }
  }, []);

  const loadDailyHours = useCallback(async (date?: string) => {
    try {
      const hours = await api.getDailyHours(date);
      setDailyHours(hours);
    } catch (err) {
      console.error('Failed to load daily hours:', err);
    }
  }, []);

  const loadWeeklySummary = useCallback(async () => {
    try {
      const summary = await api.getWeeklySummary();
      setWeeklySummary(summary);
    } catch (err) {
      console.error('Failed to load weekly summary:', err);
    }
  }, []);

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await Promise.all([loadTeamStatus(), loadDailyHours(selectedDate), loadWeeklySummary()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  }, [loadTeamStatus, loadDailyHours, loadWeeklySummary, selectedDate]);

  useEffect(() => {
    // Check auth and admin role
    if (!api.isAuthenticated()) {
      router.push('/login');
      return;
    }
    if (!api.isAdmin()) {
      router.push('/chat');
      return;
    }
    loadAllData();
  }, [router, loadAllData]);

  const handleExport = async () => {
    try {
      const today = new Date();
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      const startDate = startOfMonth.toISOString().split('T')[0];
      const endDate = today.toISOString().split('T')[0];

      const blob = await api.exportTimesheet(startDate, endDate);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `timesheet_${startDate}_to_${endDate}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      setError('Failed to export timesheet');
    }
  };

  const handleDateChange = async (date: string) => {
    setSelectedDate(date);
    await loadDailyHours(date);
  };

  const onlineCount = teamStatus.filter((m) => m.is_online).length;
  const totalHoursToday = dailyHours.reduce((sum, h) => sum + h.hours_worked, 0);
  const totalHoursWeek = weeklySummary.reduce((sum, s) => sum + s.total_hours, 0);

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <header className="h-14 border-b border-[var(--border)] flex items-center px-4 gap-4 bg-[var(--background-secondary)]">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push('/chat')}
          aria-label="Back to chat"
        >
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <Image src="/images/logo_zan.png" alt="Zantara" width={32} height={32} />
        <span className="font-semibold text-[var(--foreground)]">Admin Dashboard</span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadAllData} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="w-4 h-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="p-4 bg-[var(--error)]/10 border-b border-[var(--error)]/20">
          <p className="text-sm text-[var(--error)] text-center">{error}</p>
        </div>
      )}

      {/* Stats cards */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10">
              <Users className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-[var(--foreground-muted)]">Team Online</p>
              <p className="text-2xl font-bold text-[var(--foreground)]">
                {onlineCount} / {teamStatus.length}
              </p>
            </div>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10">
              <Clock className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-[var(--foreground-muted)]">Hours Today</p>
              <p className="text-2xl font-bold text-[var(--foreground)]">
                {totalHoursToday.toFixed(1)}h
              </p>
            </div>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10">
              <TrendingUp className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-[var(--foreground-muted)]">Hours This Week</p>
              <p className="text-2xl font-bold text-[var(--foreground)]">
                {totalHoursWeek.toFixed(1)}h
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-6">
        <div className="flex gap-2 border-b border-[var(--border)]">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'overview'
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
            }`}
          >
            <Users className="w-4 h-4 inline mr-2" />
            Team Status
          </button>
          <button
            onClick={() => setActiveTab('daily')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'daily'
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
            }`}
          >
            <Clock className="w-4 h-4 inline mr-2" />
            Daily Hours
          </button>
          <button
            onClick={() => setActiveTab('weekly')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'weekly'
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
            }`}
          >
            <Calendar className="w-4 h-4 inline mr-2" />
            Weekly Summary
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--foreground-muted)]" />
          </div>
        ) : (
          <>
            {/* Team Status Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-[var(--foreground)]">
                  Team Members ({teamStatus.length})
                </h2>
                <div className="grid gap-3">
                  {teamStatus.length === 0 ? (
                    <p className="text-[var(--foreground-muted)] py-8 text-center">
                      No team members found
                    </p>
                  ) : (
                    teamStatus.map((member) => (
                      <div
                        key={member.user_id}
                        className="p-4 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)] flex items-center gap-4"
                      >
                        <Circle
                          className={`w-3 h-3 ${
                            member.is_online
                              ? 'fill-green-500 text-green-500'
                              : 'fill-gray-400 text-gray-400'
                          }`}
                        />
                        <div className="flex-1">
                          <p className="font-medium text-[var(--foreground)]">
                            {member.email.split('@')[0]}
                          </p>
                          <p className="text-sm text-[var(--foreground-muted)]">{member.email}</p>
                        </div>
                        <div className="text-right">
                          <p
                            className={`text-sm font-medium ${
                              member.is_online ? 'text-green-500' : 'text-[var(--foreground-muted)]'
                            }`}
                          >
                            {member.is_online ? 'Online' : 'Offline'}
                          </p>
                          {member.last_action && (
                            <p className="text-xs text-[var(--foreground-muted)]">
                              Last: {new Date(member.last_action).toLocaleTimeString()}
                            </p>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Daily Hours Tab */}
            {activeTab === 'daily' && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <h2 className="text-lg font-semibold text-[var(--foreground)]">Daily Hours</h2>
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => handleDateChange(e.target.value)}
                    className="px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm"
                  />
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)]">
                          Team Member
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)]">
                          Clock In
                        </th>
                        <th className="px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)]">
                          Clock Out
                        </th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-[var(--foreground-muted)]">
                          Hours Worked
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {dailyHours.length === 0 ? (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-4 py-8 text-center text-[var(--foreground-muted)]"
                          >
                            No records for this date
                          </td>
                        </tr>
                      ) : (
                        dailyHours.map((record, index) => (
                          <tr key={index} className="border-b border-[var(--border)]">
                            <td className="px-4 py-3">
                              <p className="font-medium text-[var(--foreground)]">
                                {record.email.split('@')[0]}
                              </p>
                              <p className="text-xs text-[var(--foreground-muted)]">
                                {record.email}
                              </p>
                            </td>
                            <td className="px-4 py-3 text-[var(--foreground)]">
                              {record.clock_in
                                ? new Date(record.clock_in).toLocaleTimeString()
                                : '-'}
                            </td>
                            <td className="px-4 py-3 text-[var(--foreground)]">
                              {record.clock_out
                                ? new Date(record.clock_out).toLocaleTimeString()
                                : '-'}
                            </td>
                            <td className="px-4 py-3 text-right font-medium text-[var(--foreground)]">
                              {record.hours_worked.toFixed(2)}h
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Weekly Summary Tab */}
            {activeTab === 'weekly' && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-[var(--foreground)]">Weekly Summary</h2>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)]">
                          Team Member
                        </th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-[var(--foreground-muted)]">
                          Days Worked
                        </th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-[var(--foreground-muted)]">
                          Total Hours
                        </th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-[var(--foreground-muted)]">
                          Avg Hours/Day
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {weeklySummary.length === 0 ? (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-4 py-8 text-center text-[var(--foreground-muted)]"
                          >
                            No data for this week
                          </td>
                        </tr>
                      ) : (
                        weeklySummary.map((summary, index) => (
                          <tr key={index} className="border-b border-[var(--border)]">
                            <td className="px-4 py-3">
                              <p className="font-medium text-[var(--foreground)]">
                                {summary.email.split('@')[0]}
                              </p>
                              <p className="text-xs text-[var(--foreground-muted)]">
                                {summary.email}
                              </p>
                            </td>
                            <td className="px-4 py-3 text-center text-[var(--foreground)]">
                              {summary.days_worked}
                            </td>
                            <td className="px-4 py-3 text-center font-medium text-[var(--foreground)]">
                              {summary.total_hours.toFixed(1)}h
                            </td>
                            <td className="px-4 py-3 text-right text-[var(--foreground)]">
                              {summary.avg_hours_per_day.toFixed(1)}h
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

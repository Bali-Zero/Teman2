'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import {
  Users,
  MessageSquare,
  Clock,
  Briefcase,
  Download,
  ArrowLeft,
  Loader2,
  RefreshCw,
  Search,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  Calendar,
  Mail,
  BookOpen,
  Eye,
  Layers,
} from 'lucide-react';
import { logger } from '@/lib/logger';

type TabType = 'overview' | 'messages' | 'timesheet' | 'crm';

interface OverviewStats {
  total_conversations: number;
  total_messages: number;
  total_team_members: number;
  active_today: number;
  messages_today: number;
  total_kg_nodes?: number;
  total_kg_edges?: number;
}

interface TopUser {
  user_id: string;
  msg_count: number;
}

interface TeamMemberStat {
  email: string;
  name: string | null;
  role: string | null;
  department: string | null;
  conversations: number;
  messages: number;
  days_worked: number;
  crm_actions: number;
  emails_sent: number;
  emails_received: number;
  kb_views: number;
  kb_downloads: number;
  last_activity: string | null;
}

interface MessageItem {
  conversation_id: number;
  user_id: string | null;
  role: string | null;
  content: string | null;
  message_timestamp: string | null;
  conversation_started: string;
}

interface TimesheetRecord {
  id: number;
  email: string;
  action_type: string;
  timestamp: string;
  notes: string | null;
}

interface CrmAction {
  id: number;
  performed_by: string;
  action: string;
  entity_type: string;
  entity_id: number;
  description: string | null;
  performed_at: string;
}

export default function TeamActivityPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Overview data
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [topUsers, setTopUsers] = useState<TopUser[]>([]);
  const [teamStats, setTeamStats] = useState<TeamMemberStat[]>([]);

  // Messages data
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [messagesTotal, setMessagesTotal] = useState(0);
  const [messagesPage, setMessagesPage] = useState(0);
  const [messageFilters, setMessageFilters] = useState({
    user_id: '',
    search: '',
    role: '',
  });

  // Timesheet data
  const [timesheet, setTimesheet] = useState<TimesheetRecord[]>([]);
  const [timesheetTotal, setTimesheetTotal] = useState(0);
  const [timesheetPage, setTimesheetPage] = useState(0);
  const [timesheetFilter, setTimesheetFilter] = useState('');

  // CRM data
  const [crmActions, setCrmActions] = useState<CrmAction[]>([]);
  const [crmTotal, setCrmTotal] = useState(0);
  const [crmPage, setCrmPage] = useState(0);
  const [crmFilter, setCrmFilter] = useState('');

  const LIMIT = 50;

  // Start counting from January 5, 2026
  const START_DATE = '2026-01-05';

  const loadOverview = useCallback(async () => {
    try {
      const [overviewRes, statsRes] = await Promise.all([
        api.adminApi.getTeamActivityOverview(START_DATE),
        api.adminApi.getTeamStats(30, START_DATE),
      ]);
      setStats(overviewRes.stats);
      setTopUsers(overviewRes.top_users);
      setTeamStats(statsRes.team_stats);
    } catch (err) {
      logger.error(
        'Failed to load overview:',
        {},
        err instanceof Error ? err : new Error(String(err))
      );
      throw err;
    }
  }, []);

  const loadMessages = useCallback(async () => {
    try {
      const res = await api.adminApi.getTeamActivityMessages({
        user_id: messageFilters.user_id || undefined,
        search: messageFilters.search || undefined,
        role: messageFilters.role || undefined,
        limit: LIMIT,
        offset: messagesPage * LIMIT,
      });
      setMessages(res.messages);
      setMessagesTotal(res.total);
    } catch (err) {
      logger.error(
        'Failed to load messages:',
        {},
        err instanceof Error ? err : new Error(String(err))
      );
    }
  }, [messageFilters, messagesPage]);

  const loadTimesheet = useCallback(async () => {
    try {
      const res = await api.adminApi.getTeamTimesheet({
        email: timesheetFilter || undefined,
        limit: LIMIT,
        offset: timesheetPage * LIMIT,
      });
      setTimesheet(res.records);
      setTimesheetTotal(res.total);
    } catch (err) {
      logger.error(
        'Failed to load timesheet:',
        {},
        err instanceof Error ? err : new Error(String(err))
      );
    }
  }, [timesheetFilter, timesheetPage]);

  const loadCrmActions = useCallback(async () => {
    try {
      const res = await api.adminApi.getCrmActions({
        email: crmFilter || undefined,
        limit: LIMIT,
        offset: crmPage * LIMIT,
      });
      setCrmActions(res.actions);
      setCrmTotal(res.total);
    } catch (err) {
      logger.error(
        'Failed to load CRM actions:',
        {},
        err instanceof Error ? err : new Error(String(err))
      );
    }
  }, [crmFilter, crmPage]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  }, [loadOverview]);

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push('/login');
      return;
    }
    if (!api.isAdmin()) {
      router.push('/chat');
      return;
    }
    loadData();
  }, [router, loadData]);

  useEffect(() => {
    if (activeTab === 'messages') loadMessages();
  }, [activeTab, loadMessages]);

  useEffect(() => {
    if (activeTab === 'timesheet') loadTimesheet();
  }, [activeTab, loadTimesheet]);

  useEffect(() => {
    if (activeTab === 'crm') loadCrmActions();
  }, [activeTab, loadCrmActions]);

  const handleExportMessages = async () => {
    try {
      const blob = await api.adminApi.exportMessages({
        user_id: messageFilters.user_id || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `messages_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      logger.error('Export failed:', {}, err instanceof Error ? err : new Error(String(err)));
      setError('Failed to export messages');
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <header className="h-14 border-b border-[var(--border)] flex items-center px-4 gap-4 bg-[var(--background-secondary)]">
        <Button variant="ghost" size="icon" onClick={() => router.push('/chat')}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <Image src="/assets/logo/logo_zan.png" alt="Zantara" width={32} height={32} />
        <span className="font-semibold text-[var(--foreground)]">Team Activity Dashboard</span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadData} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="p-4 bg-red-500/10 border-b border-red-500/20">
          <p className="text-sm text-red-500 text-center">{error}</p>
        </div>
      )}

      {/* Stats cards */}
      {stats && (
        <div className="p-6 grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard
            icon={<MessageSquare className="w-5 h-5 text-blue-500" />}
            label="Total Messages"
            value={stats.total_messages.toLocaleString('en-US')}
            bgColor="bg-blue-500/10"
          />
          <StatCard
            icon={<Users className="w-5 h-5 text-green-500" />}
            label="Team Members"
            value={stats.total_team_members.toString()}
            bgColor="bg-green-500/10"
          />
          <StatCard
            icon={<TrendingUp className="w-5 h-5 text-purple-500" />}
            label="Conversations"
            value={stats.total_conversations.toLocaleString('en-US')}
            bgColor="bg-purple-500/10"
          />
          <StatCard
            icon={<Clock className="w-5 h-5 text-orange-500" />}
            label="Active Today"
            value={stats.active_today.toString()}
            bgColor="bg-orange-500/10"
          />
          <StatCard
            icon={<Calendar className="w-5 h-5 text-cyan-500" />}
            label="Messages Today"
            value={stats.messages_today.toString()}
            bgColor="bg-cyan-500/10"
          />
          {stats.total_kg_nodes !== undefined && (
            <>
              <StatCard
                icon={<BookOpen className="w-5 h-5 text-amber-500" />}
                label="Knowledge Nodes"
                value={stats.total_kg_nodes.toLocaleString('en-US')}
                bgColor="bg-amber-500/10"
              />
              <StatCard
                icon={<Layers className="w-5 h-5 text-orange-500" />}
                label="Knowledge Edges"
                value={stats.total_kg_edges?.toLocaleString('en-US') || '0'}
                bgColor="bg-orange-500/10"
              />
            </>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="px-6">
        <div className="flex gap-2 border-b border-[var(--border)] overflow-x-auto">
          <TabButton active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>
            <Users className="w-4 h-4" /> Team Stats
          </TabButton>
          <TabButton active={activeTab === 'messages'} onClick={() => setActiveTab('messages')}>
            <MessageSquare className="w-4 h-4" /> Messages
          </TabButton>
          <TabButton active={activeTab === 'timesheet'} onClick={() => setActiveTab('timesheet')}>
            <Clock className="w-4 h-4" /> Timesheet
          </TabButton>
          <TabButton active={activeTab === 'crm'} onClick={() => setActiveTab('crm')}>
            <Briefcase className="w-4 h-4" /> CRM Actions
          </TabButton>
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
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {/* Top Users */}
                <div>
                  <h3 className="text-lg font-semibold mb-4">Top 10 by Messages (dal 5 gennaio)</h3>
                  <div className="grid gap-2">
                    {topUsers.map((user, i) => (
                      <div
                        key={user.user_id}
                        className="flex items-center gap-4 p-3 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)]"
                      >
                        <span className="w-6 text-center font-bold text-[var(--foreground-muted)]">
                          {i + 1}
                        </span>
                        <span className="flex-1 font-medium">{user.user_id}</span>
                        <span className="text-[var(--accent)] font-semibold">
                          {user.msg_count} msgs
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Team Stats Table */}
                <div>
                  <h3 className="text-lg font-semibold mb-4">Team Member Stats (dal 5 gennaio)</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[var(--border)]">
                          <th className="px-3 py-2 text-left">Name</th>
                          <th className="px-3 py-2 text-left">Role</th>
                          <th className="px-3 py-2 text-right">Convs</th>
                          <th className="px-3 py-2 text-right">Msgs</th>
                          <th className="px-3 py-2 text-right">Days</th>
                          <th className="px-3 py-2 text-right">CRM</th>
                          <th className="px-3 py-2 text-right" title="Emails Sent">
                            <Mail className="w-4 h-4 inline text-blue-400" /> Sent
                          </th>
                          <th className="px-3 py-2 text-right" title="Emails Received">
                            <Mail className="w-4 h-4 inline text-green-400" /> Rcvd
                          </th>
                          <th className="px-3 py-2 text-right" title="Knowledge Base Views">
                            <Eye className="w-4 h-4 inline text-purple-400" /> Views
                          </th>
                          <th className="px-3 py-2 text-right" title="Knowledge Base Downloads">
                            <Download className="w-4 h-4 inline text-orange-400" /> DL
                          </th>
                          <th className="px-3 py-2 text-left">Last Active</th>
                        </tr>
                      </thead>
                      <tbody>
                        {teamStats.map((member) => (
                          <tr key={member.email} className="border-b border-[var(--border)]/50">
                            <td className="px-3 py-2">
                              <div className="font-medium">{member.name || '-'}</div>
                              <div className="text-xs text-[var(--foreground-muted)]">
                                {member.email}
                              </div>
                            </td>
                            <td className="px-3 py-2">{member.role || '-'}</td>
                            <td className="px-3 py-2 text-right">{member.conversations}</td>
                            <td className="px-3 py-2 text-right font-semibold text-[var(--accent)]">
                              {member.messages}
                            </td>
                            <td className="px-3 py-2 text-right">{member.days_worked}</td>
                            <td className="px-3 py-2 text-right">{member.crm_actions}</td>
                            <td className="px-3 py-2 text-right text-blue-400">
                              {member.emails_sent}
                            </td>
                            <td className="px-3 py-2 text-right text-green-400">
                              {member.emails_received}
                            </td>
                            <td className="px-3 py-2 text-right text-purple-400">
                              {member.kb_views}
                            </td>
                            <td className="px-3 py-2 text-right text-orange-400">
                              {member.kb_downloads}
                            </td>
                            <td className="px-3 py-2 text-xs">
                              {formatDate(member.last_activity)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* Messages Tab */}
            {activeTab === 'messages' && (
              <div className="space-y-4">
                {/* Filters */}
                <div className="flex flex-wrap gap-3 items-center">
                  <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                    <Search className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <input
                      type="text"
                      placeholder="Search messages..."
                      value={messageFilters.search}
                      onChange={(e) =>
                        setMessageFilters((f) => ({
                          ...f,
                          search: e.target.value,
                        }))
                      }
                      onKeyDown={(e) => e.key === 'Enter' && loadMessages()}
                      className="flex-1 px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] text-sm"
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="Filter by user..."
                    value={messageFilters.user_id}
                    onChange={(e) =>
                      setMessageFilters((f) => ({
                        ...f,
                        user_id: e.target.value,
                      }))
                    }
                    className="px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] text-sm w-48"
                  />
                  <select
                    value={messageFilters.role}
                    onChange={(e) => setMessageFilters((f) => ({ ...f, role: e.target.value }))}
                    className="px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] text-sm"
                  >
                    <option value="">All roles</option>
                    <option value="user">User</option>
                    <option value="assistant">Assistant</option>
                  </select>
                  <Button size="sm" onClick={loadMessages}>
                    Apply
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleExportMessages}>
                    <Download className="w-4 h-4 mr-2" /> Export
                  </Button>
                </div>

                {/* Messages list */}
                <div className="space-y-2">
                  {messages.length === 0 ? (
                    <p className="text-center py-8 text-[var(--foreground-muted)]">
                      No messages found
                    </p>
                  ) : (
                    messages.map((msg, i) => (
                      <div
                        key={`${msg.conversation_id}-${i}`}
                        className="p-3 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)]"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`text-xs px-2 py-0.5 rounded ${
                              msg.role === 'user'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-green-500/20 text-green-400'
                            }`}
                          >
                            {msg.role}
                          </span>
                          <span className="text-xs text-[var(--foreground-muted)]">
                            {msg.user_id}
                          </span>
                          <span className="text-xs text-[var(--foreground-muted)] ml-auto">
                            {formatDate(msg.conversation_started)}
                          </span>
                        </div>
                        <p className="text-sm whitespace-pre-wrap">
                          {msg.content?.slice(0, 300)}
                          {msg.content && msg.content.length > 300 && '...'}
                        </p>
                      </div>
                    ))
                  )}
                </div>

                {/* Pagination */}
                <Pagination
                  page={messagesPage}
                  total={messagesTotal}
                  limit={LIMIT}
                  onPrev={() => setMessagesPage((p) => Math.max(0, p - 1))}
                  onNext={() => setMessagesPage((p) => p + 1)}
                />
              </div>
            )}

            {/* Timesheet Tab */}
            {activeTab === 'timesheet' && (
              <div className="space-y-4">
                <div className="flex gap-3 items-center">
                  <input
                    type="text"
                    placeholder="Filter by email..."
                    value={timesheetFilter}
                    onChange={(e) => setTimesheetFilter(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && loadTimesheet()}
                    className="px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] text-sm w-64"
                  />
                  <Button size="sm" onClick={loadTimesheet}>
                    Apply
                  </Button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="px-3 py-2 text-left">Email</th>
                        <th className="px-3 py-2 text-left">Action</th>
                        <th className="px-3 py-2 text-left">Timestamp</th>
                        <th className="px-3 py-2 text-left">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {timesheet.length === 0 ? (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-3 py-8 text-center text-[var(--foreground-muted)]"
                          >
                            No records found
                          </td>
                        </tr>
                      ) : (
                        timesheet.map((record) => (
                          <tr key={record.id} className="border-b border-[var(--border)]/50">
                            <td className="px-3 py-2">{record.email}</td>
                            <td className="px-3 py-2">
                              <span
                                className={`px-2 py-0.5 rounded text-xs ${
                                  record.action_type === 'clock_in'
                                    ? 'bg-green-500/20 text-green-400'
                                    : 'bg-red-500/20 text-red-400'
                                }`}
                              >
                                {record.action_type}
                              </span>
                            </td>
                            <td className="px-3 py-2">{formatDate(record.timestamp)}</td>
                            <td className="px-3 py-2 text-[var(--foreground-muted)]">
                              {record.notes || '-'}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <Pagination
                  page={timesheetPage}
                  total={timesheetTotal}
                  limit={LIMIT}
                  onPrev={() => setTimesheetPage((p) => Math.max(0, p - 1))}
                  onNext={() => setTimesheetPage((p) => p + 1)}
                />
              </div>
            )}

            {/* CRM Actions Tab */}
            {activeTab === 'crm' && (
              <div className="space-y-4">
                <div className="flex gap-3 items-center">
                  <input
                    type="text"
                    placeholder="Filter by email..."
                    value={crmFilter}
                    onChange={(e) => setCrmFilter(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && loadCrmActions()}
                    className="px-3 py-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] text-sm w-64"
                  />
                  <Button size="sm" onClick={loadCrmActions}>
                    Apply
                  </Button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="px-3 py-2 text-left">User</th>
                        <th className="px-3 py-2 text-left">Action</th>
                        <th className="px-3 py-2 text-left">Entity</th>
                        <th className="px-3 py-2 text-left">Description</th>
                        <th className="px-3 py-2 text-left">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {crmActions.length === 0 ? (
                        <tr>
                          <td
                            colSpan={5}
                            className="px-3 py-8 text-center text-[var(--foreground-muted)]"
                          >
                            No actions found
                          </td>
                        </tr>
                      ) : (
                        crmActions.map((action) => (
                          <tr key={action.id} className="border-b border-[var(--border)]/50">
                            <td className="px-3 py-2">{action.performed_by}</td>
                            <td className="px-3 py-2">
                              <span className="px-2 py-0.5 rounded text-xs bg-[var(--accent)]/20 text-[var(--accent)]">
                                {action.action}
                              </span>
                            </td>
                            <td className="px-3 py-2">
                              {action.entity_type} #{action.entity_id}
                            </td>
                            <td className="px-3 py-2 text-[var(--foreground-muted)]">
                              {action.description || '-'}
                            </td>
                            <td className="px-3 py-2">{formatDate(action.performed_at)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <Pagination
                  page={crmPage}
                  total={crmTotal}
                  limit={LIMIT}
                  onPrev={() => setCrmPage((p) => Math.max(0, p - 1))}
                  onNext={() => setCrmPage((p) => p + 1)}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Helper components
function StatCard({
  icon,
  label,
  value,
  bgColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  bgColor: string;
}) {
  return (
    <div className="p-4 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)]">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${bgColor}`}>{icon}</div>
        <div>
          <p className="text-xs text-[var(--foreground-muted)]">{label}</p>
          <p className="text-xl font-bold text-[var(--foreground)]">{value}</p>
        </div>
      </div>
    </div>
  );
}

function TabButton({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
        active
          ? 'border-[var(--accent)] text-[var(--accent)]'
          : 'border-transparent text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
      }`}
    >
      {children}
    </button>
  );
}

function Pagination({
  page,
  total,
  limit,
  onPrev,
  onNext,
}: {
  page: number;
  total: number;
  limit: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  const totalPages = Math.ceil(total / limit);
  const start = page * limit + 1;
  const end = Math.min((page + 1) * limit, total);

  return (
    <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
      <span className="text-sm text-[var(--foreground-muted)]">
        Showing {start}-{end} of {total}
      </span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={onPrev} disabled={page === 0}>
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <span className="px-3 py-1 text-sm">
          {page + 1} / {totalPages || 1}
        </span>
        <Button size="sm" variant="outline" onClick={onNext} disabled={page >= totalPages - 1}>
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

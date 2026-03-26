'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  User,
  FileText,
  DollarSign,
  Globe,
  Users,
  FolderOpen,
  Building2,
  AlertCircle,
  Bell,
  MessageCircle,
  Send,
  Loader2,
  AlertTriangle,
  Activity,
  Mail,
  PenLine,
  Phone,
  Calendar,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import type {
  ClientProfile,
  FamilyMember,
  ClientDocument,
  Interaction,
  DocumentCategory,
} from '@/lib/api/crm/crm.types';
import { getCountryFlag } from '@/lib/utils/nationality-flags';

// Local component imports
import type { TabType, ModalType } from './components/types';
import { getTeamMemberAvatar } from './components/constants';
import { formatCurrency } from './components/utils';
import { OverviewTab } from './components/OverviewTab';
import { DocumentsTab } from './components/DocumentsTab';
import { ProcessTab } from './components/ProcessTab';
import { FamilyTab } from './components/FamilyTab';
import { ImmigrationTab } from './components/ImmigrationTab';
import { CompanyTab } from './components/CompanyTab';
import { TaxTab } from './components/TaxTab';
import { TimelineTab } from './components/TimelineTab';
import { EditClientModal } from './components/modals/EditClientModal';
import { AddFamilyMemberModal } from './components/modals/AddFamilyMemberModal';
import { EditFamilyMemberModal } from './components/modals/EditFamilyMemberModal';
import { AddDocumentModal } from './components/modals/AddDocumentModal';
import { EditDocumentModal } from './components/modals/EditDocumentModal';

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const clientId = params?.id ? Number(params.id) : 0;

  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [docCategories, setDocCategories] = useState<DocumentCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [activeModal, setActiveModal] = useState<ModalType>('none');
  const [editingDocument, setEditingDocument] = useState<ClientDocument | null>(null);
  const [editingFamilyMember, setEditingFamilyMember] = useState<FamilyMember | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [showStatusMenu, setShowStatusMenu] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [showLogPanel, setShowLogPanel] = useState(false);
  const [logType, setLogType] = useState<
    'note' | 'call' | 'whatsapp' | 'email' | 'meeting' | 'chat'
  >('note');
  const [logSummary, setLogSummary] = useState('');
  const [isLogging, setIsLogging] = useState(false);
  const [logSaved, setLogSaved] = useState(false);
  const logTextareaRef = useRef<HTMLTextAreaElement>(null);

  const refreshProfile = async () => {
    try {
      const profileData = await api.crm.getClientProfile(clientId);
      setProfile(profileData);
    } catch (err) {
      logger.error('Failed to refresh client data:', {}, err as Error);
    }
  };

  const submitLog = async () => {
    if (!logSummary.trim()) return;
    setIsLogging(true);
    try {
      const user = await api.getProfile();
      const newInteraction = await api.crm.createInteraction({
        client_id: clientId,
        interaction_type: logType,
        summary: logSummary.trim(),
        team_member: user.email,
        direction: 'outbound',
      });
      setInteractions((prev) => [newInteraction, ...prev]);
      toast.success('Interaction logged');
      setLogSaved(true);
      setTimeout(() => setLogSaved(false), 1500);
      setLogSummary('');
      setShowLogPanel(false);
      // Refresh to update last_interaction_date in header
      refreshProfile();
    } catch (err) {
      toast.error('Failed to log interaction', { description: (err as Error).message });
    } finally {
      setIsLogging(false);
    }
  };

  const updateStatus = async (newStatus: string) => {
    if (newStatus === profile?.client.status) {
      setShowStatusMenu(false);
      return;
    }
    setIsUpdatingStatus(true);
    setShowStatusMenu(false);
    try {
      const user = await api.getProfile();
      await api.crm.updateClient(clientId, { status: newStatus }, user.email);
      await refreshProfile();
      toast.success(`Status updated to ${newStatus}`);
    } catch (err) {
      toast.error('Failed to update status', { description: (err as Error).message });
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  // Close status menu on outside click
  useEffect(() => {
    if (!showStatusMenu) return;
    const handleClick = () => setShowStatusMenu(false);
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showStatusMenu]);

  // Fix hydration mismatch: only render dates on client
  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    Promise.all([
      api.crm.getClientProfile(clientId),
      api.crm.getClientTimeline(clientId, 50),
      api.crm.getDocumentCategories().catch(() => []),
    ])
      .then(([profileData, interactionsData, categoriesData]) => {
        if (cancelled) return;
        setProfile(profileData);
        setInteractions(interactionsData);
        setDocCategories(categoriesData);
      })
      .catch((err) => {
        if (cancelled) return;
        logger.error('Failed to load client data:', {}, err as Error);
        setError('Failed to load client data');
        toast.error('Failed to load client data');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  // Read tab from URL params and set active tab
  useEffect(() => {
    const tabParam = searchParams?.get('tab');
    if (
      tabParam &&
      [
        'overview',
        'documents',
        'process',
        'family',
        'visas',
        'company',
        'tax',
        'timeline',
      ].includes(tabParam)
    ) {
      setActiveTab(tabParam as TabType);
    }
  }, [searchParams]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    // Return placeholder during SSR to avoid hydration mismatch
    if (!isMounted) return '...';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatTime = (dateStr: string) => {
    if (!dateStr) return '';
    // Return placeholder during SSR to avoid hydration mismatch
    if (!isMounted) return '...';
    return new Date(dateStr).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <p className="text-[var(--bz-text-2)]">{error || 'Client not found'}</p>
        <Button variant="outline" onClick={() => router.push('/clients')}>
          Back to Clients
        </Button>
      </div>
    );
  }

  const { client, family_members, documents, expiry_alerts, practices, company_links, stats } =
    profile;

  // Group documents by category
  const documentsByCategory = documents.reduce(
    (acc, doc) => {
      const cat = doc.document_category || 'other';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(doc);
      return acc;
    },
    {} as Record<string, ClientDocument[]>
  );

  // Calculate stats
  const activePractices = practices.filter(
    (p) => !['completed', 'cancelled', 'approved'].includes(p.status)
  );
  const completedPractices = practices.filter((p) => ['completed', 'approved'].includes(p.status));

  // Get country flag for fallback
  const countryFlag = getCountryFlag(client.nationality);

  return (
    <div className="space-y-6">
      {/* Expiry Alert Banner — shown when there are urgent docs */}
      {expiry_alerts.filter((a) => a.alert_color === 'expired' || a.alert_color === 'red').length >
        0 && (
        <div
          className="flex items-start gap-3 rounded-xl px-4 py-3 border"
          style={{
            background: 'rgba(239,68,68,0.08)',
            borderColor: 'rgba(239,68,68,0.3)',
          }}
        >
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-red-400">
              {expiry_alerts.filter((a) => a.alert_color === 'expired').length > 0 && (
                <span>
                  {expiry_alerts.filter((a) => a.alert_color === 'expired').length} expired
                  {expiry_alerts.filter((a) => a.alert_color === 'red').length > 0 ? ' · ' : ''}
                </span>
              )}
              {expiry_alerts.filter((a) => a.alert_color === 'red').length > 0 && (
                <span>
                  {expiry_alerts.filter((a) => a.alert_color === 'red').length} expiring soon
                </span>
              )}
            </p>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {expiry_alerts
                .filter((a) => a.alert_color === 'expired' || a.alert_color === 'red')
                .slice(0, 4)
                .map((alert, i) => (
                  <span
                    key={i}
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      alert.alert_color === 'expired'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-orange-500/20 text-orange-400'
                    }`}
                  >
                    {alert.document_type?.replace(/_/g, ' ')}
                    {alert.entity_type === 'family_member' ? ` (${alert.entity_name})` : ''}
                    {alert.alert_color === 'expired'
                      ? ' — expired'
                      : ` — ${alert.days_until_expiry}d`}
                  </span>
                ))}
              {expiry_alerts.filter((a) => a.alert_color === 'expired' || a.alert_color === 'red')
                .length > 4 && (
                <span className="text-xs text-red-400 opacity-70">
                  +
                  {expiry_alerts.filter(
                    (a) => a.alert_color === 'expired' || a.alert_color === 'red'
                  ).length - 4}{' '}
                  more
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} aria-label="Go back">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex items-center gap-4 flex-1">
          {/* Avatar */}
          <div className="w-16 h-16 rounded-full bg-[var(--bz-accent)]/20 flex items-center justify-center overflow-hidden">
            {client.avatar_url ? (
              <img
                src={client.avatar_url}
                alt={client.full_name}
                className="w-full h-full object-cover"
              />
            ) : countryFlag ? (
              <div className="w-full h-full rounded-full bg-[var(--bz-base)] flex items-center justify-center text-4xl">
                {countryFlag}
              </div>
            ) : (
              <div
                className="w-full h-full rounded-full"
                style={{ background: 'var(--bz-card)' }}
              />
            )}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold text-[var(--bz-text-1)]">{client.full_name}</h1>
              {/* Status badge — click to change */}
              <div className="relative">
                <button
                  onClick={() => setShowStatusMenu((v) => !v)}
                  disabled={isUpdatingStatus}
                  className={`text-xs px-2 py-0.5 rounded-full font-medium cursor-pointer hover:opacity-80 transition-opacity disabled:cursor-wait ${
                    {
                      lead: 'bg-blue-500/20 text-blue-400',
                      active: 'bg-green-500/20 text-green-400',
                      completed: 'bg-purple-500/20 text-purple-400',
                      lost: 'bg-red-500/20 text-red-400',
                      inactive: 'bg-gray-500/20 text-gray-400',
                    }[client.status] || 'bg-gray-500/20 text-gray-400'
                  }`}
                  title="Click to change status"
                >
                  {isUpdatingStatus ? '...' : client.status}
                </button>
                {showStatusMenu && (
                  <div className="absolute top-full left-0 mt-1 z-50 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] shadow-xl py-1 min-w-[120px]">
                    {(['lead', 'active', 'completed', 'lost', 'inactive'] as const).map((s) => (
                      <button
                        key={s}
                        onClick={() => updateStatus(s)}
                        className={`w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--bz-card)] transition-colors ${
                          s === client.status ? 'font-bold' : ''
                        } ${
                          {
                            lead: 'text-blue-400',
                            active: 'text-green-400',
                            completed: 'text-purple-400',
                            lost: 'text-red-400',
                            inactive: 'text-gray-400',
                          }[s]
                        }`}
                      >
                        {s === client.status ? '✓ ' : ''}
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <p className="text-sm text-[var(--bz-text-2)]">
              Client #{client.id} • {client.client_type || 'Individual'}
              {client.company_name && ` • ${client.company_name}`}
              {isMounted &&
                client.last_interaction_date &&
                (() => {
                  const days = Math.floor(
                    (Date.now() - new Date(client.last_interaction_date).getTime()) / 86400000
                  );
                  if (days > 30) return <span className="text-red-400"> • Silent {days}d</span>;
                  if (days > 14) return <span className="text-yellow-400"> • {days}d ago</span>;
                  return null;
                })()}
            </p>
          </div>

          {/* Leader Avatar - Next to client name */}
          {client.assigned_to && (
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bz-surface)] border border-[var(--bz-border)]"
              title={`Assigned to: ${client.assigned_to.split('@')[0]}`}
            >
              {getTeamMemberAvatar(client.assigned_to) ? (
                <img
                  src={getTeamMemberAvatar(client.assigned_to)}
                  alt={client.assigned_to.split('@')[0]}
                  className="w-8 h-8 rounded-full object-cover ring-2 ring-green-500/30"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                  <User className="w-4 h-4 text-green-500" />
                </div>
              )}
              <div className="flex flex-col">
                <span className="text-xs text-[var(--bz-text-2)]">Assigned to</span>
                <span className="text-sm font-medium text-[var(--bz-text-1)] capitalize">
                  {client.assigned_to.split('@')[0]}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Alert badges */}
        {(stats.expired_count > 0 || stats.red_alerts > 0 || stats.yellow_alerts > 0) && (
          <div className="flex gap-2">
            {stats.expired_count > 0 && (
              <span className="px-2 py-1 text-xs rounded-full bg-red-600/30 text-red-300 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {stats.expired_count} expired
              </span>
            )}
            {stats.red_alerts > 0 && (
              <span className="px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400 flex items-center gap-1">
                <Bell className="w-3 h-3" />
                {stats.red_alerts} urgent
              </span>
            )}
            {stats.yellow_alerts > 0 && (
              <span className="px-2 py-1 text-xs rounded-full bg-yellow-500/20 text-yellow-400 flex items-center gap-1">
                <Bell className="w-3 h-3" />
                {stats.yellow_alerts} soon
              </span>
            )}
          </div>
        )}

        {/* Quick Actions */}
        <div className="flex gap-2">
          {client.phone && (
            <>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 text-green-500 border-green-500/30 hover:bg-green-500/10"
                onClick={() => {
                  const phone = client.phone?.replace(/\D/g, '');
                  if (phone)
                    window.open(
                      `https://wa.me/${phone.startsWith('0') ? '62' + phone.slice(1) : phone}`,
                      '_blank'
                    );
                }}
              >
                <MessageCircle className="w-4 h-4" />
                WhatsApp
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 text-sky-500 border-sky-500/30 hover:bg-sky-500/10"
                onClick={() => {
                  const phone = client.phone?.replace(/\D/g, '');
                  if (phone)
                    window.open(
                      `https://t.me/+${phone.startsWith('0') ? '62' + phone.slice(1) : phone}`,
                      '_blank'
                    );
                }}
              >
                <Send className="w-4 h-4" />
                Telegram
              </Button>
            </>
          )}
          {client.email && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-indigo-400 border-indigo-400/30 hover:bg-indigo-400/10"
              onClick={() => window.open(`mailto:${client.email}`, '_blank')}
            >
              <Mail className="w-4 h-4" />
              Email
            </Button>
          )}
          <Button
            variant={showLogPanel ? 'default' : 'outline'}
            size="sm"
            className="gap-2"
            onClick={() => {
              setShowLogPanel((v) => !v);
              if (!showLogPanel) setTimeout(() => logTextareaRef.current?.focus(), 80);
            }}
          >
            <PenLine className="w-4 h-4" />
            Log
          </Button>
          {client.google_drive_folder_id && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-amber-400 border-amber-400/30 hover:bg-amber-400/10"
              onClick={() =>
                window.open(
                  `https://drive.google.com/drive/folders/${client.google_drive_folder_id}`,
                  '_blank'
                )
              }
              title="Open client's Google Drive folder"
            >
              <FolderOpen className="w-4 h-4" />
              Drive
            </Button>
          )}
        </div>
      </div>

      {/* Inline Log Interaction Panel */}
      {showLogPanel && (
        <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-4 space-y-3 animate-in slide-in-from-top-2 duration-150">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-[var(--bz-text-1)]">Log interaction</p>
            <button
              onClick={() => {
                setShowLogPanel(false);
                setLogSummary('');
              }}
              className="p-1 rounded hover:bg-[var(--bz-card)] text-[var(--bz-text-2)]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {/* Quick presets — one click to prefill + submit */}
          <div className="flex flex-wrap gap-1.5">
            <span className="text-[10px] text-[var(--bz-text-2)] self-center mr-1 uppercase tracking-wide font-medium">Quick:</span>
            {(
              [
                { type: 'call' as const, label: '📞 Called', summary: 'Called client' },
                { type: 'call' as const, label: '📵 No answer', summary: 'Called — no answer' },
                { type: 'whatsapp' as const, label: '💬 WA sent', summary: 'WhatsApp message sent' },
                { type: 'note' as const, label: '✅ Updated', summary: 'Process updated' },
              ]
            ).map(({ type, label, summary }) => (
              <button
                key={label}
                onClick={async () => {
                  setLogType(type);
                  setLogSummary(summary);
                  setIsLogging(true);
                  try {
                    const user = await api.getProfile();
                    const newInteraction = await api.crm.createInteraction({
                      client_id: clientId,
                      interaction_type: type,
                      summary,
                      team_member: user.email,
                      direction: 'outbound',
                    });
                    setInteractions((prev) => [newInteraction, ...prev]);
                    toast.success('Logged: ' + summary);
                    setLogSaved(true);
                    setTimeout(() => setLogSaved(false), 1500);
                    setLogSummary('');
                    setShowLogPanel(false);
                    refreshProfile();
                  } catch (err) {
                    toast.error('Failed to log', { description: (err as Error).message });
                  } finally {
                    setIsLogging(false);
                  }
                }}
                disabled={isLogging}
                className="text-xs px-2.5 py-1 rounded-full border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-2)] hover:border-[var(--bz-accent)]/50 hover:text-[var(--bz-text-1)] transition-colors disabled:opacity-50"
              >
                {label}
              </button>
            ))}
          </div>
          {/* Type chips */}
          <div className="flex flex-wrap gap-2">
            {(
              [
                { key: 'note', label: 'Note', Icon: FileText },
                { key: 'call', label: 'Call', Icon: Phone },
                { key: 'whatsapp', label: 'WhatsApp', Icon: MessageCircle },
                { key: 'email', label: 'Email', Icon: Mail },
                { key: 'meeting', label: 'Meeting', Icon: Calendar },
                { key: 'chat', label: 'Chat', Icon: MessageCircle },
              ] as const
            ).map(({ key, label, Icon }) => (
              <button
                key={key}
                onClick={() => setLogType(key)}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-colors ${
                  logType === key
                    ? 'bg-[var(--bz-accent)] text-white border-[var(--bz-accent)]'
                    : 'bg-[var(--bz-base)] text-[var(--bz-text-2)] border-[var(--bz-border)] hover:border-[var(--bz-accent)]/50'
                }`}
              >
                <Icon className="w-3 h-3" />
                {label}
              </button>
            ))}
          </div>
          {/* Summary textarea */}
          <textarea
            ref={logTextareaRef}
            value={logSummary}
            onChange={(e) => setLogSummary(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitLog();
            }}
            placeholder={`Add a ${logType} note… (⌘↵ to save)`}
            rows={3}
            className="w-full rounded-lg bg-[var(--bz-base)] border border-[var(--bz-border)] text-sm text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-2)] px-3 py-2 resize-none focus:outline-none focus:border-[var(--bz-accent)] transition-colors"
          />
          <div className="flex items-center justify-between">
            <span
              className={`text-[10px] tabular-nums transition-colors ${
                logSummary.length > 400
                  ? 'text-red-400'
                  : logSummary.length > 200
                    ? 'text-yellow-400'
                    : 'text-[var(--bz-text-2)]'
              }`}
            >
              {logSummary.length > 0 ? `${logSummary.length} chars` : ''}
            </span>
            <Button
              size="sm"
              disabled={!logSummary.trim() || isLogging}
              onClick={submitLog}
              className={`gap-2 transition-colors ${logSaved ? 'bg-green-600 hover:bg-green-700' : ''}`}
            >
              {isLogging ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <PenLine className="w-4 h-4" />
              )}
              {logSaved ? 'Saved!' : 'Save'}
            </Button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[var(--bz-border)] pb-2 overflow-x-auto">
        {[
          { key: 'overview', label: 'Overview', icon: User },
          {
            key: 'documents',
            label: `Documents (${stats.documents_count})`,
            icon: FileText,
          },
          {
            key: 'process',
            label: `Process (${stats.practices_count ?? activePractices.length + completedPractices.length})`,
            icon: FolderOpen,
          },
          {
            key: 'family',
            label: `Family (${stats.family_count})`,
            icon: Users,
          },
          { key: 'visas', label: 'Immigration', icon: Globe },
          { key: 'company', label: 'Company', icon: Building2 },
          { key: 'tax', label: 'Tax', icon: DollarSign },
          {
            key: 'timeline',
            label: `Timeline (${interactions.length})`,
            icon: Activity,
          },
        ].map(({ key, label, icon: Icon }) => (
          <Button
            key={key}
            variant={activeTab === key ? 'default' : 'ghost'}
            size="sm"
            className="gap-2 whitespace-nowrap"
            onClick={() => setActiveTab(key as TabType)}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <OverviewTab
          client={client}
          stats={stats}
          documents={documents}
          activePractices={activePractices}
          completedPractices={completedPractices}
          interactions={interactions}
          formatDate={formatDate}
          formatCurrency={formatCurrency}
          router={router}
          onEditClick={() => setActiveModal('edit_client')}
          onRefresh={refreshProfile}
          clientId={clientId}
        />
      )}

      {activeTab === 'documents' && (
        <DocumentsTab
          clientId={clientId}
          documents={documents}
          documentsByCategory={documentsByCategory}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_document')}
          onEditClick={(doc) => {
            setEditingDocument(doc);
            setActiveModal('edit_document');
          }}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'process' && (
        <ProcessTab
          clientId={clientId}
          practices={[...activePractices, ...completedPractices]}
          formatDate={formatDate}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'family' && (
        <FamilyTab
          clientId={clientId}
          familyMembers={family_members}
          documents={documents}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_family')}
          onEditClick={(member) => {
            setEditingFamilyMember(member);
            setActiveModal('edit_family');
          }}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'visas' && (
        <ImmigrationTab
          clientId={clientId}
          documents={documents}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_document')}
          onEditClick={(doc) => {
            setEditingDocument(doc);
            setActiveModal('edit_document');
          }}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'company' && (
        <CompanyTab
          clientId={clientId}
          client={client}
          documents={documents}
          formatDate={formatDate}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'tax' && <TaxTab clientId={clientId} formatDate={formatDate} />}

      {activeTab === 'timeline' && (
        <TimelineTab interactions={interactions} formatDate={formatDate} formatTime={formatTime} />
      )}

      {/* Modals */}
      {activeModal === 'edit_client' && profile && (
        <EditClientModal
          client={profile.client}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'add_family' && (
        <AddFamilyMemberModal
          clientId={clientId}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'edit_family' && editingFamilyMember && (
        <EditFamilyMemberModal
          clientId={clientId}
          member={editingFamilyMember}
          onClose={() => {
            setActiveModal('none');
            setEditingFamilyMember(null);
          }}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'add_document' && (
        <AddDocumentModal
          clientId={clientId}
          categories={docCategories}
          familyMembers={family_members}
          clientHasDriveFolder={!!client.google_drive_folder_id}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'edit_document' && editingDocument && (
        <EditDocumentModal
          clientId={clientId}
          document={editingDocument}
          categories={docCategories}
          familyMembers={family_members}
          onClose={() => {
            setActiveModal('none');
            setEditingDocument(null);
          }}
          onSave={refreshProfile}
        />
      )}
    </div>
  );
}

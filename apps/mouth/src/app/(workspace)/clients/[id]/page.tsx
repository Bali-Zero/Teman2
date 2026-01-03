'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  MessageCircle,
  MapPin,
  Calendar,
  FileText,
  DollarSign,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Building2,
  Globe,
  CreditCard,
  Users,
  FolderOpen,
  Bell,
  ExternalLink,
  Plus,
  Trash2,
  Edit2,
  AlertCircle,
  Send,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type {
  ClientProfile,
  FamilyMember,
  ClientDocument,
  ExpiryAlert,
  Practice,
  Interaction,
} from '@/lib/api/crm/crm.types';

// Status badge colors
const STATUS_COLORS: Record<string, string> = {
  inquiry: 'bg-blue-500/20 text-blue-400',
  quotation_sent: 'bg-yellow-500/20 text-yellow-400',
  payment_pending: 'bg-orange-500/20 text-orange-400',
  in_progress: 'bg-purple-500/20 text-purple-400',
  waiting_documents: 'bg-pink-500/20 text-pink-400',
  submitted_to_gov: 'bg-indigo-500/20 text-indigo-400',
  approved: 'bg-emerald-500/20 text-emerald-400',
  completed: 'bg-green-500/20 text-green-400',
};

// Alert color styles
const ALERT_COLORS: Record<string, string> = {
  green: 'bg-green-500/20 text-green-400 border-green-500/30',
  yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  red: 'bg-red-500/20 text-red-400 border-red-500/30',
  expired: 'bg-red-600/30 text-red-300 border-red-600/50',
};

// Document category colors
const CATEGORY_COLORS: Record<string, string> = {
  immigration: 'bg-blue-500/20 text-blue-400',
  pma: 'bg-purple-500/20 text-purple-400',
  tax: 'bg-emerald-500/20 text-emerald-400',
  personal: 'bg-orange-500/20 text-orange-400',
  other: 'bg-gray-500/20 text-gray-400',
};

const INTERACTION_ICONS: Record<string, React.ReactNode> = {
  chat: <MessageCircle className="w-4 h-4" />,
  email: <Mail className="w-4 h-4" />,
  whatsapp: <MessageCircle className="w-4 h-4 text-green-500" />,
  call: <Phone className="w-4 h-4" />,
  meeting: <Calendar className="w-4 h-4" />,
  note: <FileText className="w-4 h-4" />,
};

type TabType = 'overview' | 'family' | 'documents' | 'cases' | 'timeline';

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clientId = Number(params.id);

  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [profileData, interactionsData] = await Promise.all([
          api.crm.getClientProfile(clientId),
          api.crm.getClientTimeline(clientId, 20),
        ]);
        setProfile(profileData);
        setInteractions(interactionsData);
      } catch (err) {
        console.error('Failed to load client data:', err);
        setError('Failed to load client data');
      } finally {
        setIsLoading(false);
      }
    };

    if (clientId) {
      loadData();
    }
  }, [clientId]);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <p className="text-[var(--foreground-muted)]">{error || 'Client not found'}</p>
        <Button variant="outline" onClick={() => router.push('/clients')}>
          Back to Clients
        </Button>
      </div>
    );
  }

  const { client, family_members, documents, expiry_alerts, practices, stats } = profile;

  // Group documents by category
  const documentsByCategory = documents.reduce((acc, doc) => {
    const cat = doc.document_category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(doc);
    return acc;
  }, {} as Record<string, ClientDocument[]>);

  // Calculate stats
  const activePractices = practices.filter(
    (p) => !['completed', 'cancelled', 'approved'].includes(p.status)
  );
  const completedPractices = practices.filter((p) =>
    ['completed', 'approved'].includes(p.status)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex items-center gap-4 flex-1">
          {/* Avatar */}
          <div className="w-16 h-16 rounded-full bg-[var(--accent)]/20 flex items-center justify-center overflow-hidden">
            {client.avatar_url ? (
              <img src={client.avatar_url} alt={client.full_name} className="w-full h-full object-cover" />
            ) : (
              <User className="w-8 h-8 text-[var(--accent)]" />
            )}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--foreground)]">{client.full_name}</h1>
            <p className="text-sm text-[var(--foreground-muted)]">
              Client #{client.id} • {client.client_type || 'Individual'}
              {client.company_name && ` • ${client.company_name}`}
            </p>
          </div>
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
                  window.open(`https://wa.me/${phone}`, '_blank');
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
                  window.open(`https://t.me/+${phone}`, '_blank');
                }}
              >
                <Send className="w-4 h-4" />
                Telegram
              </Button>
            </>
          )}
          {client.google_drive_folder_id && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-blue-500 border-blue-500/30 hover:bg-blue-500/10"
              onClick={() => window.open(`https://drive.google.com/drive/folders/${client.google_drive_folder_id}`, '_blank')}
            >
              <FolderOpen className="w-4 h-4" />
              Drive
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[var(--border)] pb-2">
        {[
          { key: 'overview', label: 'Overview', icon: User },
          { key: 'family', label: `Family (${stats.family_count})`, icon: Users },
          { key: 'documents', label: `Documents (${stats.documents_count})`, icon: FileText },
          { key: 'cases', label: `Cases (${stats.practices_count})`, icon: FolderOpen },
          { key: 'timeline', label: 'Timeline', icon: Clock },
        ].map(({ key, label, icon: Icon }) => (
          <Button
            key={key}
            variant={activeTab === key ? 'default' : 'ghost'}
            size="sm"
            className="gap-2"
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
          expiry_alerts={expiry_alerts}
          activePractices={activePractices}
          completedPractices={completedPractices}
          formatDate={formatDate}
          formatCurrency={formatCurrency}
          router={router}
        />
      )}

      {activeTab === 'family' && (
        <FamilyTab
          clientId={clientId}
          familyMembers={family_members}
          formatDate={formatDate}
        />
      )}

      {activeTab === 'documents' && (
        <DocumentsTab
          clientId={clientId}
          documentsByCategory={documentsByCategory}
          formatDate={formatDate}
        />
      )}

      {activeTab === 'cases' && (
        <CasesTab
          clientId={clientId}
          practices={practices}
          formatDate={formatDate}
          formatCurrency={formatCurrency}
          router={router}
        />
      )}

      {activeTab === 'timeline' && (
        <TimelineTab
          interactions={interactions}
          formatDate={formatDate}
          formatTime={formatTime}
        />
      )}
    </div>
  );
}

// ============================================
// OVERVIEW TAB
// ============================================
function OverviewTab({
  client,
  stats,
  expiry_alerts,
  activePractices,
  completedPractices,
  formatDate,
  formatCurrency,
  router,
}: {
  client: ClientProfile['client'];
  stats: ClientProfile['stats'];
  expiry_alerts: ExpiryAlert[];
  activePractices: ClientProfile['practices'];
  completedPractices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Column - Client Info */}
      <div className="space-y-6">
        {/* Client Info Card */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Contact Info</h3>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="gap-1 text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                onClick={() => {
                  // TODO: Open edit modal
                  alert('Edit client coming soon - use API for now');
                }}
              >
                <Edit2 className="w-4 h-4" />
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1 text-[var(--foreground-muted)] hover:text-red-500"
                onClick={async () => {
                  if (confirm(`⚠️ Delete client "${client.full_name}"?\n\nThis will mark the client as inactive. All cases and documents remain in the system.\n\nContinue?`)) {
                    try {
                      const user = await api.getProfile();
                      await api.crm.deleteClient(client.id, user.email);
                      alert('Client deleted (marked as inactive)');
                      router.push('/clients');
                    } catch (err) {
                      alert('Error deleting client: ' + (err as Error).message);
                    }
                  }
                }}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>
          <div className="space-y-3">
            {/* LEAD - Most important field */}
            {client.assigned_to && (
              <div className="flex items-center gap-3 text-sm">
                <User className="w-4 h-4 text-[var(--accent)]" />
                <span className="text-[var(--foreground)]">
                  <span className="text-[var(--foreground-muted)]">Lead:</span>{' '}
                  <span className="font-medium text-[var(--accent)]">{client.assigned_to.split('@')[0]}</span>
                </span>
              </div>
            )}
            {client.email && (
              <div className="flex items-center gap-3 text-sm">
                <Mail className="w-4 h-4 text-[var(--foreground-muted)]" />
                <span className="text-[var(--foreground)]">{client.email}</span>
              </div>
            )}
            {client.phone && (
              <div className="flex items-center gap-3 text-sm">
                <Phone className="w-4 h-4 text-[var(--foreground-muted)]" />
                <span className="text-[var(--foreground)]">{client.phone}</span>
              </div>
            )}
            {client.nationality && (
              <div className="flex items-center gap-3 text-sm">
                <Globe className="w-4 h-4 text-[var(--foreground-muted)]" />
                <span className="text-[var(--foreground)]">{client.nationality}</span>
              </div>
            )}
            {client.passport_number && (
              <div className="flex items-center gap-3 text-sm">
                <CreditCard className="w-4 h-4 text-[var(--foreground-muted)]" />
                <span className="text-[var(--foreground)]">
                  {client.passport_number}
                  {client.passport_expiry && (
                    <span className="text-[var(--foreground-muted)] ml-2">
                      (exp: {formatDate(client.passport_expiry)})
                    </span>
                  )}
                </span>
              </div>
            )}
            {client.address && (
              <div className="flex items-center gap-3 text-sm">
                <MapPin className="w-4 h-4 text-[var(--foreground-muted)]" />
                <span className="text-[var(--foreground)]">{client.address}</span>
              </div>
            )}
            {client.company_name && (
              <div className="flex items-center gap-3 text-sm">
                <Building2 className="w-4 h-4 text-[var(--foreground-muted)]" />
                <span className="text-[var(--foreground)]">{client.company_name}</span>
              </div>
            )}
          </div>

          {client.notes && (
            <div className="mt-4 pt-4 border-t border-[var(--border)]">
              <p className="text-xs text-[var(--foreground-muted)] mb-1">Notes</p>
              <p className="text-sm text-[var(--foreground)]">{client.notes}</p>
            </div>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Users className="w-4 h-4 text-blue-500" />
              <span className="text-xs text-[var(--foreground-muted)]">Family</span>
            </div>
            <p className="text-2xl font-bold text-[var(--foreground)]">{stats.family_count}</p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-purple-500" />
              <span className="text-xs text-[var(--foreground-muted)]">Documents</span>
            </div>
            <p className="text-2xl font-bold text-[var(--foreground)]">{stats.documents_count}</p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-purple-500" />
              <span className="text-xs text-[var(--foreground-muted)]">Active Cases</span>
            </div>
            <p className="text-2xl font-bold text-[var(--foreground)]">{activePractices.length}</p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <span className="text-xs text-[var(--foreground-muted)]">Completed</span>
            </div>
            <p className="text-2xl font-bold text-[var(--foreground)]">{completedPractices.length}</p>
          </div>
        </div>
      </div>

      {/* Middle Column - Expiry Alerts */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
          <Bell className="w-5 h-5" />
          Expiry Alerts
        </h3>
        {expiry_alerts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
            <CheckCircle2 className="w-8 h-8 mx-auto text-green-500 mb-2" />
            <p className="text-sm text-[var(--foreground-muted)]">No expiring documents</p>
          </div>
        ) : (
          <div className="space-y-2">
            {expiry_alerts.map((alert, idx) => (
              <div
                key={`${alert.entity_type}-${alert.entity_id}-${idx}`}
                className={`rounded-lg border p-3 ${ALERT_COLORS[alert.alert_color] || 'bg-gray-500/20'}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium">{alert.entity_name}</span>
                  <span className="text-xs">
                    {alert.alert_color === 'expired'
                      ? 'EXPIRED'
                      : `${alert.days_until_expiry}d left`}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs opacity-80">
                  <span>{alert.document_type}</span>
                  <span>{formatDate(alert.expiry_date)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right Column - Active Cases */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-[var(--foreground)]">Active Cases</h3>
          <Button
            size="sm"
            className="gap-2"
            onClick={() => router.push(`/cases/new?client_id=${client.id}`)}
          >
            <Plus className="w-4 h-4" />
            New
          </Button>
        </div>
        {activePractices.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
            <FolderOpen className="w-8 h-8 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
            <p className="text-sm text-[var(--foreground-muted)]">No active cases</p>
          </div>
        ) : (
          <div className="space-y-2">
            {activePractices.map((practice) => (
              <div
                key={practice.id}
                className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3 hover:border-[var(--accent)]/50 group"
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className="text-sm font-medium text-[var(--foreground)] cursor-pointer flex-1"
                    onClick={() => router.push(`/cases/${practice.id}`)}
                  >
                    {practice.practice_type_name}
                  </span>
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        STATUS_COLORS[practice.status] || 'bg-gray-500/20 text-gray-400'
                      }`}
                    >
                      {practice.status.replace(/_/g, ' ')}
                    </span>
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity ml-1">
                      <button
                        onClick={() => router.push(`/cases/${practice.id}/edit`)}
                        className="p-1 rounded hover:bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                        title="Edit"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={async () => {
                          if (confirm(`Delete case "${practice.practice_type_name}"?\n\nThis will mark the case as cancelled.`)) {
                            try {
                              const user = await api.getProfile();
                              await api.crm.deletePractice(practice.id, user.email);
                              alert('Case deleted');
                              window.location.reload();
                            } catch (err) {
                              alert('Error: ' + (err as Error).message);
                            }
                          }
                        }}
                        className="p-1 rounded hover:bg-red-500/20 text-[var(--foreground-muted)] hover:text-red-500"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
                {practice.expiry_date && (
                  <div className="text-xs text-[var(--foreground-muted)]">
                    Expires: {formatDate(practice.expiry_date)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================
// FAMILY TAB
// ============================================
function FamilyTab({
  clientId,
  familyMembers,
  formatDate,
}: {
  clientId: number;
  familyMembers: FamilyMember[];
  formatDate: (d: string) => string;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Family Members</h3>
        <Button size="sm" className="gap-2">
          <Plus className="w-4 h-4" />
          Add Member
        </Button>
      </div>

      {familyMembers.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Users className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No family members added yet</p>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Add spouse, children, or dependents
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {familyMembers.map((member) => (
            <div
              key={member.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                    <User className="w-5 h-5 text-[var(--accent)]" />
                  </div>
                  <div>
                    <h4 className="font-medium text-[var(--foreground)]">{member.full_name}</h4>
                    <p className="text-xs text-[var(--foreground-muted)] capitalize">
                      {member.relationship}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Edit2 className="w-4 h-4" />
                </Button>
              </div>

              <div className="space-y-2 text-sm">
                {member.nationality && (
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span>{member.nationality}</span>
                  </div>
                )}
                {member.passport_number && (
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span>
                      {member.passport_number}
                      {member.passport_expiry && (
                        <span
                          className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                            ALERT_COLORS[member.passport_alert || 'green']
                          }`}
                        >
                          {formatDate(member.passport_expiry)}
                        </span>
                      )}
                    </span>
                  </div>
                )}
                {member.current_visa_type && (
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span>
                      {member.current_visa_type}
                      {member.visa_expiry && (
                        <span
                          className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                            ALERT_COLORS[member.visa_alert || 'green']
                          }`}
                        >
                          {formatDate(member.visa_expiry)}
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// DOCUMENTS TAB
// ============================================
function DocumentsTab({
  clientId,
  documentsByCategory,
  formatDate,
}: {
  clientId: number;
  documentsByCategory: Record<string, ClientDocument[]>;
  formatDate: (d: string) => string;
}) {
  const categoryNames: Record<string, string> = {
    immigration: 'Immigration Documents',
    pma: 'PT PMA Documents',
    tax: 'Tax Documents',
    personal: 'Personal Documents',
    other: 'Other Documents',
  };

  const categoryOrder = ['immigration', 'pma', 'tax', 'personal', 'other'];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Documents</h3>
        <Button size="sm" className="gap-2">
          <Plus className="w-4 h-4" />
          Add Document
        </Button>
      </div>

      {Object.keys(documentsByCategory).length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <FileText className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No documents uploaded yet</p>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Upload passport, KITAS, PT PMA documents, and more
          </p>
        </div>
      ) : (
        categoryOrder.map((category) => {
          const docs = documentsByCategory[category];
          if (!docs || docs.length === 0) return null;

          return (
            <div key={category} className="space-y-3">
              <h4 className="font-medium text-[var(--foreground)] flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${CATEGORY_COLORS[category]}`}>
                  {categoryNames[category] || category}
                </span>
                <span className="text-[var(--foreground-muted)]">({docs.length})</span>
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {docs.map((doc) => (
                  <div
                    key={doc.id}
                    className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-[var(--foreground)]">
                        {doc.document_type.replace(/_/g, ' ')}
                      </span>
                      <div className="flex items-center gap-1">
                        {doc.google_drive_file_url && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => window.open(doc.google_drive_file_url!, '_blank')}
                          >
                            <ExternalLink className="w-3 h-3" />
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                          <Trash2 className="w-3 h-3 text-red-400" />
                        </Button>
                      </div>
                    </div>

                    {doc.file_name && (
                      <p className="text-xs text-[var(--foreground-muted)] truncate mb-1">
                        {doc.file_name}
                      </p>
                    )}

                    {doc.expiry_date && (
                      <div
                        className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${
                          ALERT_COLORS[doc.alert_color || 'green']
                        }`}
                      >
                        <Calendar className="w-3 h-3" />
                        {doc.alert_color === 'expired'
                          ? 'Expired'
                          : `Expires: ${formatDate(doc.expiry_date)}`}
                      </div>
                    )}

                    {doc.family_member_name && (
                      <p className="text-xs text-[var(--foreground-muted)] mt-1">
                        → {doc.family_member_name}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

// ============================================
// CASES TAB
// ============================================
function CasesTab({
  clientId,
  practices,
  formatDate,
  formatCurrency,
  router,
}: {
  clientId: number;
  practices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">All Cases</h3>
        <Button size="sm" className="gap-2" onClick={() => router.push(`/cases/new?client_id=${clientId}`)}>
          <Plus className="w-4 h-4" />
          New Case
        </Button>
      </div>

      {practices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <FolderOpen className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No cases yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {practices.map((practice) => (
            <div
              key={practice.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4 hover:border-[var(--accent)]/50 transition-colors group"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => router.push(`/cases/${practice.id}`)}
                >
                  <span className="text-sm font-medium text-[var(--foreground)]">
                    {practice.practice_type_name}
                  </span>
                  <span className="text-xs text-[var(--foreground-muted)] ml-2">
                    #{practice.id}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      STATUS_COLORS[practice.status] || 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {practice.status.replace(/_/g, ' ')}
                  </span>
                  {/* Edit/Delete buttons - show on hover */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/cases/${practice.id}/edit`);
                      }}
                      className="p-1 rounded hover:bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                      title="Edit case"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (confirm(`Delete case "${practice.practice_type_name}"?\n\nThis will mark the case as cancelled.`)) {
                          try {
                            const user = await api.getProfile();
                            await api.crm.deletePractice(practice.id, user.email);
                            alert('Case deleted');
                            window.location.reload();
                          } catch (err) {
                            alert('Error: ' + (err as Error).message);
                          }
                        }
                      }}
                      className="p-1 rounded hover:bg-red-500/20 text-[var(--foreground-muted)] hover:text-red-500"
                      title="Delete case"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              {practice.expiry_date && (
                <div
                  className={`text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded ${
                    ALERT_COLORS[practice.alert_color || 'green']
                  }`}
                >
                  <Calendar className="w-3 h-3" />
                  Expires: {formatDate(practice.expiry_date)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// TIMELINE TAB
// ============================================
function TimelineTab({
  interactions,
  formatDate,
  formatTime,
}: {
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatTime: (d: string) => string;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-[var(--foreground)]">Activity Timeline</h3>

      {interactions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Clock className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No activity yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {interactions.map((interaction, idx) => (
            <div key={interaction.id} className="flex gap-3">
              {/* Timeline Line */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    interaction.interaction_type === 'whatsapp'
                      ? 'bg-green-500/20 text-green-500'
                      : interaction.interaction_type === 'email'
                      ? 'bg-blue-500/20 text-blue-500'
                      : interaction.interaction_type === 'call'
                      ? 'bg-purple-500/20 text-purple-500'
                      : 'bg-[var(--accent)]/20 text-[var(--accent)]'
                  }`}
                >
                  {INTERACTION_ICONS[interaction.interaction_type] || (
                    <MessageCircle className="w-4 h-4" />
                  )}
                </div>
                {idx < interactions.length - 1 && (
                  <div className="w-0.5 h-full min-h-[40px] bg-[var(--border)]" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-4">
                <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-[var(--foreground)]">
                      {interaction.interaction_type.charAt(0).toUpperCase() +
                        interaction.interaction_type.slice(1)}
                    </span>
                    <span className="text-[10px] text-[var(--foreground-muted)]">
                      {formatDate(interaction.interaction_date)}{' '}
                      {formatTime(interaction.interaction_date)}
                    </span>
                  </div>
                  {interaction.subject && (
                    <p className="text-sm text-[var(--foreground)] mb-1">
                      {interaction.subject}
                    </p>
                  )}
                  {interaction.summary && (
                    <p className="text-xs text-[var(--foreground-muted)] line-clamp-2">
                      {interaction.summary}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2 text-[10px] text-[var(--foreground-muted)]">
                    <span>{interaction.team_member}</span>
                    {interaction.sentiment && (
                      <span
                        className={`px-1.5 py-0.5 rounded ${
                          interaction.sentiment === 'positive'
                            ? 'bg-green-500/20 text-green-400'
                            : interaction.sentiment === 'negative'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {interaction.sentiment}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
  X,
  Save,
  Upload,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import type {
  ClientProfile,
  FamilyMember,
  ClientDocument,
  ExpiryAlert,
  Practice,
  Interaction,
  Client,
  DocumentCategory,
} from '@/lib/api/crm/crm.types';
import {
  COMMON_NATIONALITIES,
  CLIENT_STATUSES,
} from '@/lib/api/crm/crm.types';
import { cropToSquare } from '@/lib/utils/imageResize';

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
type ModalType = 'none' | 'edit_client' | 'add_family' | 'add_document';

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const toast = useToast();
  const clientId = Number(params.id);

  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [docCategories, setDocCategories] = useState<DocumentCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [activeModal, setActiveModal] = useState<ModalType>('none');

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [profileData, interactionsData, categoriesData] = await Promise.all([
        api.crm.getClientProfile(clientId),
        api.crm.getClientTimeline(clientId, 20),
        api.crm.getDocumentCategories().catch(() => []),
      ]);
      setProfile(profileData);
      setInteractions(interactionsData);
      setDocCategories(categoriesData);
    } catch (err) {
      console.error('Failed to load client data:', err);
      setError('Failed to load client data');
      toast.error('Error', 'Failed to load client data');
    } finally {
      setIsLoading(false);
    }
  };

  const refreshProfile = async () => {
    try {
      const profileData = await api.crm.getClientProfile(clientId);
      setProfile(profileData);
    } catch (err) {
      console.error('Failed to refresh client data:', err);
    }
  };

  useEffect(() => {
    if (clientId) {
      loadData();
    }
  }, [clientId]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatTime = (dateStr: string) => {
    if (!dateStr) return '';
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
            ) : client.status === 'lead' ? (
              <img src="/avatars/default-lead.svg" alt="Lead" className="w-full h-full object-cover" />
            ) : client.status === 'active' ? (
              <img src="/avatars/default-active.svg" alt="Active" className="w-full h-full object-cover" />
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
                  if (phone) window.open(`https://wa.me/${phone.startsWith('0') ? '62' + phone.slice(1) : phone}`, '_blank');
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
                  if (phone) window.open(`https://t.me/+${phone.startsWith('0') ? '62' + phone.slice(1) : phone}`, '_blank');
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
      <div className="flex gap-2 border-b border-[var(--border)] pb-2 overflow-x-auto">
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
          expiry_alerts={expiry_alerts}
          activePractices={activePractices}
          completedPractices={completedPractices}
          recentInteractions={interactions}
          formatDate={formatDate}
          formatCurrency={formatCurrency}
          formatTime={formatTime}
          router={router}
          onEditClick={() => setActiveModal('edit_client')}
          onAddNote={async (note: string) => {
            const user = await api.getProfile();
            await api.crm.createInteraction({
              client_id: clientId,
              interaction_type: 'note',
              summary: note,
              team_member: user.email,
            });
            const interactionsData = await api.crm.getClientTimeline(clientId, 20);
            setInteractions(interactionsData);
            toast.success('Note Added');
          }}
        />
      )}

      {activeTab === 'family' && (
        <FamilyTab
          clientId={clientId}
          familyMembers={family_members}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_family')}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'documents' && (
        <DocumentsTab
          clientId={clientId}
          documentsByCategory={documentsByCategory}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_document')}
          onRefresh={refreshProfile}
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

      {activeModal === 'add_document' && (
        <AddDocumentModal
          clientId={clientId}
          categories={docCategories}
          familyMembers={family_members}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
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
  recentInteractions,
  formatDate,
  formatCurrency,
  formatTime,
  router,
  onEditClick,
  onAddNote,
}: {
  client: ClientProfile['client'];
  stats: ClientProfile['stats'];
  expiry_alerts: ExpiryAlert[];
  activePractices: ClientProfile['practices'];
  completedPractices: ClientProfile['practices'];
  recentInteractions: Interaction[];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  formatTime: (d: string) => string;
  router: ReturnType<typeof useRouter>;
  onEditClick: () => void;
  onAddNote: (note: string) => Promise<void>;
}) {
  const toast = useToast();
  const [quickNote, setQuickNote] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);

  const handleAddNote = async () => {
    if (!quickNote.trim()) return;
    setIsAddingNote(true);
    try {
      await onAddNote(quickNote);
      setQuickNote('');
    } catch (err) {
      toast.error('Failed', (err as Error).message);
    } finally {
      setIsAddingNote(false);
    }
  };

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
                onClick={onEditClick}
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
                      toast.success('Client deleted', 'Marked as inactive');
                      router.push('/clients');
                      router.refresh(); // Force data refetch
                    } catch (err) {
                      toast.error('Error deleting client', (err as Error).message);
                    }
                  }
                }}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>
          <div className="space-y-3">
            {/* Lead - Changed label to Consultant/Advisor */}
            {client.assigned_to && (
              <div className="flex items-center gap-3 text-sm">
                {getTeamMemberAvatar(client.assigned_to) ? (
                  <img
                    src={getTeamMemberAvatar(client.assigned_to)}
                    alt={client.assigned_to.split('@')[0]}
                    className="w-8 h-8 rounded-full object-cover ring-2 ring-[var(--accent)]/30"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                    <User className="w-4 h-4 text-[var(--accent)]" />
                  </div>
                )}
                <span className="text-[var(--foreground)]">
                  <span className="text-[var(--foreground-muted)]">Consultant:</span>{' '}
                  <span className="font-medium text-[var(--accent)]">{client.assigned_to.split('@')[0]}</span>
                </span>
              </div>
            )}
            {client.email && (
              <div className="flex items-center gap-3 text-sm">
                <Mail className="w-4 h-4 text-[var(--foreground-muted)]" />
                <a href={`mailto:${client.email}`} className="text-[var(--foreground)] hover:underline">{client.email}</a>
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
              <p className="text-sm text-[var(--foreground)] whitespace-pre-wrap">{client.notes}</p>
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

        {/* Quick Add Note */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-3 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Quick Note
          </h3>
          <div className="space-y-2">
            <textarea
              value={quickNote}
              onChange={(e) => setQuickNote(e.target.value)}
              placeholder="Add a quick note about this client..."
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 resize-none text-sm"
            />
            <Button
              size="sm"
              onClick={handleAddNote}
              disabled={!quickNote.trim() || isAddingNote}
              className="w-full gap-2"
            >
              {isAddingNote ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="w-3 h-3" />
                  Add Note
                </>
              )}
            </Button>
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

        {/* Recent Activity */}
        <div className="mt-6">
          <h3 className="text-lg font-semibold text-[var(--foreground)] flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5" />
            Recent Activity
          </h3>
          {recentInteractions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6 text-center">
              <MessageCircle className="w-6 h-6 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">No recent activity</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentInteractions.slice(0, 5).map((interaction) => (
                <div
                  key={interaction.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`w-6 h-6 rounded-full flex items-center justify-center ${ 
                        interaction.interaction_type === 'whatsapp'
                          ? 'bg-green-500/20 text-green-500'
                          : interaction.interaction_type === 'email'
                          ? 'bg-blue-500/20 text-blue-500'
                          : interaction.interaction_type === 'call'
                          ? 'bg-purple-500/20 text-purple-500'
                          : interaction.interaction_type === 'note'
                          ? 'bg-yellow-500/20 text-yellow-500'
                          : 'bg-[var(--accent)]/20 text-[var(--accent)]'
                      }`}
                    >
                      {INTERACTION_ICONS[interaction.interaction_type] || <MessageCircle className="w-3 h-3" />}
                    </span>
                    <span className="text-xs font-medium text-[var(--foreground)] flex-1">
                      {interaction.interaction_type.charAt(0).toUpperCase() +
                        interaction.interaction_type.slice(1)}
                    </span>
                    <span className="text-[10px] text-[var(--foreground-muted)]">
                      {formatDate(interaction.interaction_date)}
                    </span>
                  </div>
                  {interaction.summary && (
                    <p className="text-xs text-[var(--foreground-muted)] line-clamp-2 ml-8">
                      {interaction.summary}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
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
                              toast.success('Case deleted');
                              window.location.reload();
                            } catch (err) {
                              toast.error('Error', (err as Error).message);
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
  onAddClick,
  onRefresh,
}: {
  clientId: number;
  familyMembers: FamilyMember[];
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onRefresh: () => void;
}) {
  const toast = useToast();

  const handleDelete = async (id: number, name: string) => {
    if (confirm(`Remove ${name} from family members?`)) {
      try {
        await api.crm.deleteFamilyMember(clientId, id);
        toast.success('Family member removed');
        onRefresh();
      } catch (err) {
        toast.error('Error', (err as Error).message);
      }
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Family Members</h3>
        <Button size="sm" className="gap-2" onClick={onAddClick}>
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
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4 relative group"
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
                <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-red-400 hover:text-red-500 hover:bg-red-500/10" onClick={() => handleDelete(member.id, member.full_name)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
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
  onAddClick,
  onRefresh,
}: {
  clientId: number;
  documentsByCategory: Record<string, ClientDocument[]>;
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onRefresh: () => void;
}) {
  const toast = useToast();
  const categoryNames: Record<string, string> = {
    immigration: 'Immigration Documents',
    pma: 'PT PMA Documents',
    tax: 'Tax Documents',
    personal: 'Personal Documents',
    other: 'Other Documents',
  };

  const categoryOrder = ['immigration', 'pma', 'tax', 'personal', 'other'];

  const handleDelete = async (docId: number, fileName: string) => {
    if (confirm(`Archive document "${fileName || 'Document'}"?`)) {
      try {
        await api.crm.deleteDocument(clientId, docId);
        toast.success('Document archived');
        onRefresh();
      } catch (err) {
        toast.error('Error', (err as Error).message);
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Documents</h3>
        <Button size="sm" className="gap-2" onClick={onAddClick}>
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
                    className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3 group"
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
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-red-400 hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => handleDelete(doc.id, doc.file_name || doc.document_type)}
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>

                    {doc.file_name && (
                      <p className="text-xs text-[var(--foreground-muted)] truncate mb-1" title={doc.file_name}>
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
  const toast = useToast();
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
                            toast.success('Case deleted');
                            window.location.reload();
                          } catch (err) {
                            toast.error('Error', (err as Error).message);
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

// ============================================ 
// MODAL COMPONENTS
// ============================================ 

function Modal({
  title,
  onClose,
  children,
  isSaving,
  onSave,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  isSaving: boolean;
  onSave: (e: React.FormEvent) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[var(--background)] border border-[var(--border)] rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-[var(--border)]">
          <h2 className="text-xl font-semibold text-[var(--foreground)]">{title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={onSave} className="overflow-y-auto flex-1">
          <div className="p-6 space-y-6">{children}</div>
          <div className="flex items-center justify-end gap-3 p-6 border-t border-[var(--border)] bg-[var(--background-secondary)] mt-auto">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving} className="gap-2">
              {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// TEAM MEMBERS - Should fetch from API but hardcoded for now as per NewClientPage
const TEAM_MEMBERS = [
  { value: 'adit@balizero.com', label: 'Adit', avatar: '/avatars/team/adit.png' },
  { value: 'ari@balizero.com', label: 'Ari', avatar: '/avatars/team/ari.png' },
  { value: 'krisna@balizero.com', label: 'Krisna', avatar: '/avatars/team/krisna.png' },
  { value: 'dea@balizero.com', label: 'Dea', avatar: '/avatars/team/dea.png' },
  { value: 'zero@balizero.com', label: 'Anton' },
  { value: 'damar@balizero.com', label: 'Damar' },
  { value: 'vino@balizero.com', label: 'Vino' },
  { value: 'ruslana@balizero.com', label: 'Ruslana' },
  { value: 'veronika@balizero.com', label: 'Veronika' },
  { value: 'dewaayu@balizero.com', label: 'Dewa Ayu' },
  { value: 'faysha@balizero.com', label: 'Faysha' },
  { value: 'kadek@balizero.com', label: 'Kadek' },
  { value: 'angel@balizero.com', label: 'Angel' },
  { value: 'surya@balizero.com', label: 'Surya' },
  { value: 'sahira@balizero.com', label: 'Sahira', avatar: '/avatars/team/sahira.png' },
];

// Helper to get team member avatar
const getTeamMemberAvatar = (email: string): string | undefined => {
  return TEAM_MEMBERS.find(m => m.value === email)?.avatar;
};

function EditClientModal({ client, onClose, onSave }: { client: Client; onClose: () => void; onSave: () => void }) {
  const [isSaving, setIsSaving] = useState(false);
  const toast = useToast();
  const [formData, setFormData] = useState({
    full_name: client.full_name || '',
    email: client.email || '',
    phone: client.phone || '',
    whatsapp: client.whatsapp || '',
    company_name: client.company_name || '',
    nationality: client.nationality || '',
    passport_number: client.passport_number || '',
    passport_expiry: client.passport_expiry?.split('T')[0] || '',
    address: client.address || '',
    notes: client.notes || '',
    status: client.status || 'lead',
    client_type: client.client_type || 'individual',
    assigned_to: client.assigned_to || '',
    avatar_url: client.avatar_url || '',
  });

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert('Image size must be less than 2MB');
      return;
    }

    try {
      // Crop to square and resize to 400x400px
      const resizedImage = await cropToSquare(file, 400, 0.85);
      setFormData((prev) => ({ ...prev, avatar_url: resizedImage }));
    } catch (error) {
      console.error('Failed to process image:', error);
      alert('Failed to process image. Please try again.');
    }
  };

  const removeAvatar = () => {
    setFormData((prev) => ({ ...prev, avatar_url: '' }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name.trim()) return alert('Full name is required');
    setIsSaving(true);
    try {
      const user = await api.getProfile();
      const updates: Record<string, string> = {};
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== undefined && value !== null) updates[key] = value;
      });
      await api.crm.updateClient(client.id, updates, user.email);
      onSave();
      onClose();
      toast.success('Client updated');
    } catch (err) {
      toast.error('Failed to update', (err as Error).message);
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass = 'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)]';

  return (
    <Modal title="Edit Client" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      {/* Avatar Upload */}
      <div className="flex items-center gap-6 pb-6 border-b border-[var(--border)]">
        <div className="relative">
          <div className="w-24 h-24 rounded-full overflow-hidden border-2 border-[var(--border)] bg-[var(--background-secondary)] flex items-center justify-center">
            {formData.avatar_url ? (
              <img
                src={formData.avatar_url}
                alt="Avatar preview"
                className="w-full h-full object-cover"
              />
            ) : formData.status === 'lead' ? (
              <img src="/avatars/default-lead.svg" alt="Default Lead" className="w-full h-full object-cover" />
            ) : formData.status === 'active' ? (
              <img src="/avatars/default-active.svg" alt="Default Active" className="w-full h-full object-cover" />
            ) : (
              <User className="w-12 h-12 text-[var(--foreground-muted)]" />
            )}
          </div>
          {formData.avatar_url && (
            <button
              type="button"
              onClick={removeAvatar}
              className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Client Photo</label>
          <p className="text-xs text-[var(--foreground-muted)] mb-2">
            Upload a profile picture (max 2MB)
          </p>
          <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent)]/90 transition-colors cursor-pointer">
            <Upload className="w-4 h-4" />
            {formData.avatar_url ? 'Change Photo' : 'Upload Photo'}
            <input
              type="file"
              accept="image/*"
              onChange={handleAvatarUpload}
              className="hidden"
            />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Full Name *</label>
          <input type="text" value={formData.full_name} onChange={e => setFormData({...formData, full_name: e.target.value})} className={inputClass} required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Email</label>
          <input type="email" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Phone</label>
          <input type="tel" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Nationality</label>
          <select value={formData.nationality} onChange={e => setFormData({...formData, nationality: e.target.value})} className={inputClass}>
            <option value="">Select...</option>
            {COMMON_NATIONALITIES.map(nat => <option key={nat} value={nat}>{nat}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Assigned To</label>
          <select value={formData.assigned_to} onChange={e => setFormData({...formData, assigned_to: e.target.value})} className={inputClass}>
            <option value="">Unassigned</option>
            {TEAM_MEMBERS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Status</label>
          <div className="flex gap-2 flex-wrap">
            {CLIENT_STATUSES.map(({ value, label, color }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFormData({ ...formData, status: value })}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all border ${ 
                  formData.status === value
                    ? `border-${color}-500/50`
                    : 'border-transparent bg-[var(--background-secondary)]'
                }`}
                style={{ 
                  backgroundColor: formData.status === value ? `var(--${color === 'blue' ? 'accent' : color}-500-20, rgba(59, 130, 246, 0.2))` : undefined,
                  color: formData.status === value ? `var(--${color === 'blue' ? 'accent' : color}-500, #3b82f6)` : 'var(--foreground-muted)',
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function AddFamilyMemberModal({ clientId, onClose, onSave }: { clientId: number; onClose: () => void; onSave: () => void }) {
  const [isSaving, setIsSaving] = useState(false);
  const toast = useToast();
  const [formData, setFormData] = useState({
    full_name: '',
    relationship: 'spouse',
    nationality: '',
    passport_number: '',
    passport_expiry: '',
    current_visa_type: '',
    visa_expiry: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name) return;
    setIsSaving(true);
    try {
      await api.crm.createFamilyMember(clientId, formData);
      toast.success('Family member added');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to add', (err as Error).message);
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass = 'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50';

  return (
    <Modal title="Add Family Member" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Full Name *</label>
          <input type="text" value={formData.full_name} onChange={e => setFormData({...formData, full_name: e.target.value})} className={inputClass} required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Relationship</label>
          <select value={formData.relationship} onChange={e => setFormData({...formData, relationship: e.target.value})} className={inputClass}>
            <option value="spouse">Spouse</option>
            <option value="child">Child</option>
            <option value="parent">Parent</option>
            <option value="dependent">Dependent</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Nationality</label>
          <select value={formData.nationality} onChange={e => setFormData({...formData, nationality: e.target.value})} className={inputClass}>
            <option value="">Select...</option>
            {COMMON_NATIONALITIES.map(nat => <option key={nat} value={nat}>{nat}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Number</label>
          <input type="text" value={formData.passport_number} onChange={e => setFormData({...formData, passport_number: e.target.value.toUpperCase()})} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Expiry</label>
          <input type="date" value={formData.passport_expiry} onChange={e => setFormData({...formData, passport_expiry: e.target.value})} className={inputClass} />
        </div>
      </div>
    </Modal>
  );
}

function AddDocumentModal({ clientId, categories, familyMembers, onClose, onSave }: { clientId: number; categories: DocumentCategory[]; familyMembers: FamilyMember[]; onClose: () => void; onSave: () => void }) {
  const [isSaving, setIsSaving] = useState(false);
  const toast = useToast();
  const [formData, setFormData] = useState({
    file_name: '',
    document_type: '',
    document_category: 'other',
    expiry_date: '',
    google_drive_file_url: '',
    family_member_id: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) return;
    setIsSaving(true);
    try {
      await api.crm.createDocument(clientId, {
        ...formData,
        family_member_id: formData.family_member_id ? Number(formData.family_member_id) : undefined,
      });
      toast.success('Document added');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to add', (err as Error).message);
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass = 'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50';

  return (
    <Modal title="Add Document" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Document Name *</label>
          <input type="text" value={formData.file_name} onChange={e => setFormData({...formData, file_name: e.target.value})} className={inputClass} placeholder="e.g. Passport Scan" required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Category</label>
          <select value={formData.document_category} onChange={e => setFormData({...formData, document_category: e.target.value})} className={inputClass}>
            <option value="immigration">Immigration</option>
            <option value="pma">Company (PMA)</option>
            <option value="tax">Tax</option>
            <option value="personal">Personal</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Type</label>
          <input type="text" value={formData.document_type} onChange={e => setFormData({...formData, document_type: e.target.value})} className={inputClass} placeholder="passport, kitas, etc" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Expiry Date</label>
          <input type="date" value={formData.expiry_date} onChange={e => setFormData({...formData, expiry_date: e.target.value})} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Belongs To</label>
          <select value={formData.family_member_id} onChange={e => setFormData({...formData, family_member_id: e.target.value})} className={inputClass}>
            <option value="">Main Client</option>
            {familyMembers.map(m => <option key={m.id} value={m.id}>{m.full_name} ({m.relationship})</option>)}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Google Drive Link</label>
          <input type="url" value={formData.google_drive_file_url} onChange={e => setFormData({...formData, google_drive_file_url: e.target.value})} className={inputClass} placeholder="https://drive.google.com/..." />
        </div>
      </div>
    </Modal>
  );
}
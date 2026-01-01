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
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { Client, Practice, Interaction } from '@/lib/api/crm/crm.types';

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

const INTERACTION_ICONS: Record<string, React.ReactNode> = {
  chat: <MessageCircle className="w-4 h-4" />,
  email: <Mail className="w-4 h-4" />,
  whatsapp: <MessageCircle className="w-4 h-4 text-green-500" />,
  call: <Phone className="w-4 h-4" />,
  meeting: <Calendar className="w-4 h-4" />,
  note: <FileText className="w-4 h-4" />,
};

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clientId = Number(params.id);

  const [client, setClient] = useState<Client | null>(null);
  const [practices, setPractices] = useState<Practice[]>([]);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [clientData, practicesData, interactionsData] = await Promise.all([
          api.crm.getClient(clientId),
          api.crm.getClientPractices(clientId),
          api.crm.getClientTimeline(clientId, 20),
        ]);
        setClient(clientData);
        setPractices(practicesData);
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

  // Calculate stats
  const activePractices = practices.filter(
    (p) => !['completed', 'cancelled', 'approved'].includes(p.status)
  );
  const completedPractices = practices.filter((p) =>
    ['completed', 'approved'].includes(p.status)
  );
  const totalRevenue = practices.reduce((sum, p) => sum + (p.actual_price || p.quoted_price || 0), 0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  if (error || !client) {
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-[var(--foreground)]">{client.full_name}</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Client #{client.id} • {client.client_type || 'Individual'}
          </p>
        </div>
        {/* Quick Actions */}
        <div className="flex gap-2">
          {client.phone && (
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
          )}
          {client.email && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-blue-500 border-blue-500/30 hover:bg-blue-500/10"
              onClick={() => window.open(`mailto:${client.email}`, '_blank')}
            >
              <Mail className="w-4 h-4" />
              Email
            </Button>
          )}
          {client.phone && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-purple-500 border-purple-500/30 hover:bg-purple-500/10"
              onClick={() => window.open(`tel:${client.phone}`, '_blank')}
            >
              <Phone className="w-4 h-4" />
              Call
            </Button>
          )}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Client Info + Stats */}
        <div className="space-y-6">
          {/* Client Info Card */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                <User className="w-8 h-8 text-[var(--accent)]" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-[var(--foreground)]">
                  {client.full_name}
                </h2>
                {client.assigned_to && (
                  <p className="text-sm text-[var(--accent)]">
                    Lead: {client.assigned_to.split('@')[0]}
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-3">
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
                  <span className="text-[var(--foreground)]">{client.passport_number}</span>
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
                <FileText className="w-4 h-4 text-[var(--accent)]" />
                <span className="text-xs text-[var(--foreground-muted)]">Total Cases</span>
              </div>
              <p className="text-2xl font-bold text-[var(--foreground)]">{practices.length}</p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-purple-500" />
                <span className="text-xs text-[var(--foreground-muted)]">Active</span>
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
            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-4 h-4 text-emerald-500" />
                <span className="text-xs text-[var(--foreground-muted)]">Revenue</span>
              </div>
              <p className="text-lg font-bold text-[var(--foreground)]">
                {formatCurrency(totalRevenue)}
              </p>
            </div>
          </div>
        </div>

        {/* Middle Column - Cases */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Cases</h3>
            <Button
              size="sm"
              className="gap-2"
              onClick={() => router.push(`/cases/new?client_id=${clientId}`)}
            >
              <FileText className="w-4 h-4" />
              New Case
            </Button>
          </div>

          <div className="space-y-3">
            {practices.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
                <FileText className="w-8 h-8 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
                <p className="text-sm text-[var(--foreground-muted)]">No cases yet</p>
              </div>
            ) : (
              practices.map((practice) => (
                <div
                  key={practice.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4 cursor-pointer hover:border-[var(--accent)]/50 transition-colors"
                  onClick={() => router.push(`/cases/${practice.id}`)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-[var(--foreground)]">
                      {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ')}
                    </span>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        STATUS_COLORS[practice.status] || 'bg-gray-500/20 text-gray-400'
                      }`}
                    >
                      {practice.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-[var(--foreground-muted)]">
                    <span>#{practice.id}</span>
                    {practice.quoted_price && (
                      <span>{formatCurrency(practice.quoted_price)}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column - Timeline */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-[var(--foreground)]">Activity Timeline</h3>

          <div className="space-y-1">
            {interactions.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
                <Clock className="w-8 h-8 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
                <p className="text-sm text-[var(--foreground-muted)]">No activity yet</p>
              </div>
            ) : (
              interactions.map((interaction, idx) => (
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
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

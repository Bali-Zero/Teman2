'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  User,
  Edit2,
  Users,
  FileText,
  MessageCircle,
  Mail,
  Phone,
  Send,
  Calendar,
  Clock,
  Activity,
  FolderOpen,
  CheckCircle2,
  ArrowRight,
  Copy,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ClientProfile, ClientDocument, Interaction } from '@/lib/api/crm/crm.types';
import { formatPhoneNumber, isBirthdayToday } from './utils';
import { PassportCard } from './PassportCard';
import { VisaCard } from './VisaCard';

const INTERACTION_ICONS: Record<string, typeof MessageCircle> = {
  chat: MessageCircle,
  whatsapp: MessageCircle,
  email: Mail,
  call: Phone,
  telegram: Send,
  meeting: Calendar,
  note: FileText,
};

const SENTIMENT_COLORS: Record<string, string> = {
  positive: 'text-green-400',
  neutral: 'text-gray-400',
  negative: 'text-red-400',
};

export function OverviewTab({
  client,
  stats,
  documents,
  activePractices,
  completedPractices,
  interactions,
  formatDate,
  formatCurrency,
  router,
  onEditClick,
  onRefresh,
  clientId,
}: {
  client: ClientProfile['client'];
  stats: ClientProfile['stats'];
  documents: ClientDocument[];
  activePractices: ClientProfile['practices'];
  completedPractices: ClientProfile['practices'];
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  router: ReturnType<typeof useRouter>;
  onEditClick: () => void;
  onRefresh: () => Promise<void>;
  clientId: number;
}) {
  const isClientBirthday = isBirthdayToday(client.date_of_birth);
  const [showAllInteractions, setShowAllInteractions] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = (value: string, field: string) => {
    void navigator.clipboard.writeText(value).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };
  const TIMELINE_PREVIEW = 5;
  const visibleInteractions = showAllInteractions
    ? interactions
    : interactions.slice(0, TIMELINE_PREVIEW);

  return (
    <div className="space-y-6">
      {/* 3 Columns Layout - Team Member | Passport | Visa */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        {/* COLUMN 1: Client Info */}
        <div className="flex flex-col h-full">
          {/* Client Info Card */}
          <div
            className="rounded-xl border shadow-xl backdrop-blur-xl transition-all duration-300 overflow-hidden flex-1 flex flex-col h-full hover:shadow-2xl hover:-translate-y-1"
            style={{
              border: isClientBirthday ? '1px solid rgba(251,191,36,0.4)' : '1px solid rgba(255, 255, 255, 0.05)',
              background: isClientBirthday ? 'rgba(45,38,20,0.8)' : 'rgba(32, 32, 36, 0.65)',
              boxShadow: isClientBirthday ? '0 0 24px rgba(251,191,36,0.15), 0 10px 20px -10px rgba(0,0,0,0.5)' : undefined,
            }}
          >
            <div
              className="flex items-center justify-between px-4 py-3 border-b"
              style={{ borderColor: 'rgba(255,255,255,0.05)' }}
            >
              <h3 className="font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
                Client Info
                {isClientBirthday && <span className="text-base" title="Birthday today!">🎂</span>}
              </h3>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={onEditClick}
                  aria-label="Edit client info"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
            <div className="p-4 space-y-4 flex-1">
              {/* Full Name */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-[var(--bz-accent)]/10 flex items-center justify-center">
                  <User className="w-4 h-4 text-[var(--bz-accent)]" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-[var(--bz-text-2)]">Full Name</p>
                  <p className="text-base font-semibold">{client.full_name}</p>
                </div>
              </div>

              <div className="border-t border-[var(--bz-border)]" />

              {/* Contact Info */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Email
                  </p>
                  <div className="flex items-center gap-1.5 group/copy">
                    <p className="text-sm font-medium truncate">
                      {client.email || (
                        <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                      )}
                    </p>
                    {client.email && (
                      <button
                        onClick={() => copyToClipboard(client.email!, 'email')}
                        className="opacity-0 group-hover/copy:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--bz-card)]"
                        title="Copy email"
                      >
                        {copiedField === 'email' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-[var(--bz-text-2)]" />}
                      </button>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Phone
                  </p>
                  <div className="flex items-center gap-1.5 group/copy">
                    <p className="text-sm font-medium">
                      {client.phone ? (
                        formatPhoneNumber(client.phone)
                      ) : (
                        <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                      )}
                    </p>
                    {client.phone && (
                      <button
                        onClick={() => copyToClipboard(client.phone!, 'phone')}
                        className="opacity-0 group-hover/copy:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--bz-card)]"
                        title="Copy phone"
                      >
                        {copiedField === 'phone' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-[var(--bz-text-2)]" />}
                      </button>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Nationality
                  </p>
                  <p className="text-sm font-medium">
                    {client.nationality || (
                      <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Gender
                  </p>
                  <p className="text-sm font-medium">
                    {client.gender === 'M' ? (
                      'Male'
                    ) : client.gender === 'F' ? (
                      'Female'
                    ) : (
                      <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Passport & DOB - from OCR extraction */}
              {(client.passport_number || client.date_of_birth) && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    {client.passport_number && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Passport
                        </p>
                        <div className="flex items-center gap-1.5 group/copy">
                          <p className="text-sm font-semibold font-mono">{client.passport_number}</p>
                          <button
                            onClick={() => copyToClipboard(client.passport_number!, 'passport')}
                            className="opacity-0 group-hover/copy:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--bz-card)]"
                            title="Copy passport number"
                          >
                            {copiedField === 'passport' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-[var(--bz-text-2)]" />}
                          </button>
                        </div>
                      </div>
                    )}
                    {client.passport_expiry && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Passport Expiry
                        </p>
                        <p
                          className={`text-sm font-medium ${new Date(client.passport_expiry) < new Date() ? 'text-red-500' : new Date(client.passport_expiry) < new Date(Date.now() + 365 * 86400000) ? 'text-yellow-500' : 'text-green-500'}`}
                        >
                          {formatDate(client.passport_expiry)}
                        </p>
                      </div>
                    )}
                    {client.date_of_birth && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Date of Birth
                        </p>
                        <p className="text-sm font-medium">{formatDate(client.date_of_birth)}</p>
                      </div>
                    )}
                    {client.birthplace && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Birthplace
                        </p>
                        <p className="text-sm font-medium">{client.birthplace}</p>
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Address */}
              {client.address && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                      Address
                    </p>
                    <p className="text-sm font-medium">{client.address}</p>
                  </div>
                </>
              )}

              {/* Notes */}
              {client.notes && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1">
                      Notes
                    </p>
                    <p className="text-sm text-[var(--bz-text-2)] leading-relaxed whitespace-pre-line">
                      {client.notes}
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div
              className="rounded-lg border shadow-lg backdrop-blur-md p-3 transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
              style={{
                border: '1px solid rgba(255, 255, 255, 0.05)',
                background: 'rgba(35, 35, 40, 0.45)',
              }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <Users className="w-3.5 h-3.5 text-blue-500" />
                <span className="text-[10px] text-[var(--bz-text-2)]">Family</span>
              </div>
              <p className="text-lg font-bold">{stats.family_count}</p>
            </div>
            <div
              className="rounded-lg border shadow-lg backdrop-blur-md p-3 transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
              style={{
                border: '1px solid rgba(255, 255, 255, 0.05)',
                background: 'rgba(35, 35, 40, 0.45)',
              }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <FileText className="w-3.5 h-3.5 text-purple-500" />
                <span className="text-[10px] text-[var(--bz-text-2)]">Docs</span>
              </div>
              <p className="text-lg font-bold">{stats.documents_count}</p>
            </div>
          </div>
        </div>

        {/* COLUMN 2: Passport */}
        <div className="flex flex-col h-full">
          <PassportCard
            client={client}
            documents={documents}
            formatDate={formatDate}
            onRefresh={onRefresh}
            clientId={clientId}
          />
        </div>

        {/* COLUMN 3: Visa */}
        <div className="flex flex-col h-full">
          <VisaCard
            client={client}
            documents={documents}
            activePractices={activePractices}
            formatDate={formatDate}
            formatCurrency={formatCurrency}
            onRefresh={onRefresh}
            clientId={clientId}
          />
        </div>
      </div>

      {/* Bottom Section: Activity Timeline + Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Activity Timeline — spans 2 columns */}
        <div
          className="lg:col-span-2 rounded-xl border shadow-xl backdrop-blur-xl overflow-hidden"
          style={{
            border: '1px solid rgba(255, 255, 255, 0.05)',
            background: 'rgba(32, 32, 36, 0.65)',
          }}
        >
          <div
            className="flex items-center justify-between px-4 py-3 border-b"
            style={{ borderColor: 'rgba(255,255,255,0.05)' }}
          >
            <h3 className="font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--bz-accent)]" />
              Activity Timeline
            </h3>
            <span className="text-xs text-[var(--bz-text-2)]">
              {interactions.length > 0
                ? `${interactions.length} interactions`
                : 'No interactions yet'}
            </span>
          </div>

          <div className="p-4 max-h-[480px] overflow-y-auto">
            {interactions.length > 0 ? (
              <div className="space-y-1">
                {visibleInteractions.map((interaction, idx) => {
                  const Icon = INTERACTION_ICONS[interaction.interaction_type] || MessageCircle;
                  const sentimentClass = interaction.sentiment
                    ? SENTIMENT_COLORS[interaction.sentiment] || 'text-gray-400'
                    : '';

                  return (
                    <div
                      key={interaction.id}
                      className="group flex gap-3 py-2.5 px-2 rounded-lg hover:bg-white/[0.03] transition-colors"
                    >
                      {/* Timeline line + icon */}
                      <div className="flex flex-col items-center">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                            interaction.direction === 'inbound'
                              ? 'bg-blue-500/15 text-blue-400'
                              : 'bg-green-500/15 text-green-400'
                          }`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        {idx < visibleInteractions.length - 1 && (
                          <div className="w-px flex-1 bg-[var(--bz-border)] mt-1" />
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 pb-2">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-medium text-[var(--bz-text-1)] capitalize">
                            {interaction.interaction_type}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/[0.05] text-[var(--bz-text-2)]">
                            {interaction.direction === 'inbound' ? '← In' : '→ Out'}
                          </span>
                          {interaction.channel &&
                            interaction.channel !== interaction.interaction_type && (
                              <span className="text-[10px] text-[var(--bz-text-2)]">
                                via {interaction.channel}
                              </span>
                            )}
                          {interaction.sentiment && (
                            <span className={`text-[10px] ${sentimentClass}`}>
                              {interaction.sentiment}
                            </span>
                          )}
                        </div>
                        {interaction.subject && (
                          <p className="text-sm text-[var(--bz-text-1)] font-medium truncate">
                            {interaction.subject}
                          </p>
                        )}
                        {interaction.summary && (
                          <p className="text-xs text-[var(--bz-text-2)] line-clamp-2 mt-0.5">
                            {interaction.summary}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="w-3 h-3 text-[var(--bz-text-2)]" />
                          <span className="text-[10px] text-[var(--bz-text-2)]">
                            {formatDate(interaction.interaction_date)}
                          </span>
                          {interaction.team_member && (
                            <span className="text-[10px] text-[var(--bz-text-2)]">
                              • {interaction.team_member.split('@')[0]}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {interactions.length > TIMELINE_PREVIEW && (
                  <button
                    onClick={() => setShowAllInteractions((v) => !v)}
                    className="w-full mt-2 py-2 text-xs text-[var(--bz-accent)] hover:text-[var(--bz-accent)]/80 border border-[var(--bz-border)] hover:border-[var(--bz-accent)]/40 rounded-lg transition-colors"
                  >
                    {showAllInteractions
                      ? 'Show less'
                      : `Show ${interactions.length - TIMELINE_PREVIEW} more interactions`}
                  </button>
                )}
              </div>
            ) : (
              <div className="py-8 text-center">
                <MessageCircle className="w-10 h-10 mx-auto mb-3 text-[var(--bz-text-2)] opacity-30" />
                <p className="text-sm text-[var(--bz-text-2)]">No interactions recorded yet</p>
                <p className="text-xs text-[var(--bz-text-2)] mt-1 opacity-60">
                  Interactions from WhatsApp, Email, Telegram and other channels will appear here
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right column: Practices Summary */}
        <div className="space-y-4">
          {/* Active Practices */}
          <div
            className="rounded-xl border shadow-xl backdrop-blur-xl overflow-hidden"
            style={{
              border: '1px solid rgba(255, 255, 255, 0.05)',
              background: 'rgba(32, 32, 36, 0.65)',
            }}
          >
            <div
              className="flex items-center justify-between px-4 py-3 border-b"
              style={{ borderColor: 'rgba(255,255,255,0.05)' }}
            >
              <h3 className="font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-yellow-500" />
                Active
              </h3>
              <span className="text-xs font-bold text-[var(--bz-accent)]">
                {activePractices.length}
              </span>
            </div>
            <div className="p-3 space-y-2 max-h-[180px] overflow-y-auto">
              {activePractices.length > 0 ? (
                activePractices.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-white/[0.03] transition-colors cursor-pointer group/p"
                    onClick={() => router.push(`/process/${p.id}`)}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-[var(--bz-text-1)] truncate group-hover/p:text-[var(--bz-accent)] transition-colors">
                        {p.practice_type_name || `Practice #${p.id}`}
                      </p>
                      <p className="text-[10px] text-[var(--bz-text-2)]">
                        {p.status} • {p.priority}
                      </p>
                    </div>
                    {p.quoted_price != null && p.quoted_price > 0 && (
                      <span className="text-xs font-medium text-[var(--bz-accent)] ml-2 shrink-0">
                        {formatCurrency(p.quoted_price)}
                      </span>
                    )}
                    <ArrowRight className="w-3 h-3 text-[var(--bz-text-2)] ml-1 opacity-0 group-hover/p:opacity-100 transition-opacity shrink-0" />
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--bz-text-2)] text-center py-3 opacity-60">
                  No active processes
                </p>
              )}
            </div>
          </div>

          {/* Completed Practices */}
          <div
            className="rounded-xl border shadow-xl backdrop-blur-xl overflow-hidden"
            style={{
              border: '1px solid rgba(255, 255, 255, 0.05)',
              background: 'rgba(32, 32, 36, 0.65)',
            }}
          >
            <div
              className="flex items-center justify-between px-4 py-3 border-b"
              style={{ borderColor: 'rgba(255,255,255,0.05)' }}
            >
              <h3 className="font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                Completed
              </h3>
              <span className="text-xs font-bold text-green-400">{completedPractices.length}</span>
            </div>
            <div className="p-3 space-y-2 max-h-[180px] overflow-y-auto">
              {completedPractices.length > 0 ? (
                completedPractices.slice(0, 5).map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-white/[0.03] transition-colors cursor-pointer group/p"
                    onClick={() => router.push(`/process/${p.id}`)}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-[var(--bz-text-1)] truncate group-hover/p:text-green-400 transition-colors">
                        {p.practice_type_name || `Practice #${p.id}`}
                      </p>
                      {p.completion_date && (
                        <p className="text-[10px] text-[var(--bz-text-2)]">
                          Completed {formatDate(p.completion_date)}
                        </p>
                      )}
                    </div>
                    {p.actual_price != null && p.actual_price > 0 && (
                      <span className="text-xs font-medium text-green-400 ml-2 shrink-0">
                        {formatCurrency(p.actual_price)}
                      </span>
                    )}
                    <ArrowRight className="w-3 h-3 text-[var(--bz-text-2)] ml-1 opacity-0 group-hover/p:opacity-100 transition-opacity shrink-0" />
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--bz-text-2)] text-center py-3 opacity-60">
                  No completed processes
                </p>
              )}
              {completedPractices.length > 5 && (
                <p className="text-[10px] text-[var(--bz-text-2)] text-center">
                  +{completedPractices.length - 5} more
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

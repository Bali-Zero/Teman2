import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  MessageCircle,
  Clock,
  AlertCircle,
  Mail,
  Phone,
  Building2,
  BellOff,
  Tag,
  Plus,
} from 'lucide-react';
import { Client } from '@/lib/api/crm/crm.types';
import { useRouter } from 'next/navigation';

interface ClientCardProps {
  client: Client;
  isDragging?: boolean;
}

const SENTIMENT_COLORS = {
  positive: 'ring-[var(--neon-emerald)]',
  neutral: 'ring-[var(--neon-amber)]',
  negative: 'ring-[var(--neon-rose)]',
  mixed: 'ring-[var(--neon-purple)]',
  none: 'ring-[var(--glass-rim)]',
};

const SENTIMENT_BG = {
  positive: 'bg-[rgba(16,185,129,0.1)] text-[var(--neon-emerald)]',
  neutral: 'bg-[rgba(245,158,11,0.1)] text-[var(--neon-amber)]',
  negative: 'bg-[rgba(244,63,94,0.1)] text-[var(--neon-rose)]',
  mixed: 'bg-[rgba(139,92,246,0.1)] text-[var(--neon-purple)]',
  none: 'bg-[rgba(255,255,255,0.05)] text-[var(--tx-tertiary)]',
};

import { getCountryFlag } from '@/lib/utils/nationality-flags';
import {
  getTeamMemberAvatar,
  TEAM_MEMBERS,
} from '@/app/(workspace)/clients/[id]/components/constants';

export const ClientCard = React.memo(
  ({ client, isDragging }: ClientCardProps) => {
    const router = useRouter();
    const [isMounted, setIsMounted] = useState(false);

    // Fix hydration mismatch: only render dates on client
    useEffect(() => {
      setIsMounted(true);
    }, []);

    // Determine sentiment aura
    const sentiment = (
      client.last_sentiment || 'none'
    ).toLowerCase() as keyof typeof SENTIMENT_COLORS;
    const ringColor = SENTIMENT_COLORS[sentiment] || SENTIMENT_COLORS.none;
    const badgeStyle = SENTIMENT_BG[sentiment] || SENTIMENT_BG.none;

    // Get country flag for fallback
    const countryFlag = getCountryFlag(client.nationality);

    // Passport expiry alert
    const passportDaysLeft = client.passport_expiry
      ? Math.ceil((new Date(client.passport_expiry).getTime() - Date.now()) / 86400000)
      : null;
    const passportAlert =
      passportDaysLeft !== null
        ? passportDaysLeft < 0
          ? 'expired'
          : passportDaysLeft <= 180
            ? 'soon'
            : null
        : null;

    // Silence streak (days since last contact)
    const silenceDays =
      isMounted && client.last_interaction_date
        ? Math.floor((Date.now() - new Date(client.last_interaction_date).getTime()) / 86400000)
        : null;

    // Assigned team member
    const assignedMember = client.assigned_to
      ? TEAM_MEMBERS.find((m) => m.value === client.assigned_to)
      : null;
    const assignedAvatar = client.assigned_to ? getTeamMemberAvatar(client.assigned_to) : null;
    const assignedName = assignedMember?.label || client.assigned_to?.split('@')[0] || null;

    return (
      <div className="relative group perspective-1000">
        <motion.div
          // Removed layoutId to improve performance with large lists
          // layoutId causes expensive layout calculations with many items
          className={`
          relative rounded-[1.125rem] border p-4 cursor-pointer transition-all duration-300 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05),0_10px_20px_-10px_rgba(0,0,0,0.5)] backdrop-blur-xl bg-gradient-to-br from-[rgba(255,255,255,0.03)] to-[rgba(255,255,255,0.01)]
          ${isDragging ? 'opacity-50 scale-95 rotate-3' : 'hover:-translate-y-1 hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_15px_30px_-10px_rgba(0,0,0,0.6)] hover:bg-[rgba(255,255,255,0.06)]'}
        `}
          style={{
            borderColor: 'var(--glass-rim)',
          }}
          onClick={() => router.push(`/clients/${client.id}`)}
        >
          {/* Header with Avatar & Name */}
          <div className="flex items-start gap-3 mb-3">
            <div
              className={`relative w-10 h-10 rounded-full ${ringColor} ring-2 ring-offset-2 ring-offset-[var(--background-secondary)] shrink-0`}
            >
              {client.avatar_url ? (
                <img
                  src={client.avatar_url}
                  alt={client.full_name}
                  className="w-full h-full rounded-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              ) : null}
              {!client.avatar_url && (
                <div className="w-full h-full rounded-full bg-[rgba(255,255,255,0.05)] flex items-center justify-center text-[var(--tx-pure)]">
                  {countryFlag ? (
                    <span className="text-lg leading-none">{countryFlag}</span>
                  ) : (
                    <span className="text-xs font-bold opacity-80 uppercase">
                      {client.full_name
                        ?.split(' ')
                        .slice(0, 2)
                        .map((n) => n[0]?.toUpperCase())
                        .join('') || '?'}
                    </span>
                  )}
                </div>
              )}

              {/* Status Dot */}
              <div
                className={`absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-[var(--background-secondary)]
              ${
                {
                  lead: 'bg-[var(--neon-blue)]',
                  active: 'bg-[var(--neon-emerald)]',
                  completed: 'bg-[var(--neon-purple)]',
                  inactive: 'bg-[var(--tx-tertiary)]',
                  lost: 'bg-[var(--neon-rose)]',
                }[client.status] || 'bg-[var(--tx-tertiary)]'
              }`}
              />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <h4 className="font-bold text-[var(--tx-pure)] text-sm truncate">
                  {client.full_name}
                </h4>
                {client.client_type === 'company' && (
                  <span title="Company" aria-label="Company">
                    <Building2 className="w-3 h-3 shrink-0 text-[var(--tx-tertiary)]" />
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-0.5 text-[11px] text-[var(--tx-secondary)] tracking-wide">
                <span className="truncate">{client.nationality || 'Unknown'}</span>
                {client.company_name && (
                  <>
                    <span className="opacity-50">•</span>
                    <span className="truncate max-w-[80px]">{client.company_name}</span>
                  </>
                )}
              </div>
              {/* Passport alert */}
              {passportAlert && (
                <div
                  className={`mt-1 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full ${passportAlert === 'expired' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}
                  title={client.passport_expiry ? new Date(client.passport_expiry).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : undefined}
                >
                  <AlertCircle className="w-2.5 h-2.5" />
                  {passportDaysLeft !== null && passportDaysLeft < 0 ? `Passport exp ${Math.abs(passportDaysLeft)}d ago` : passportDaysLeft !== null ? `⏰ Passport ${passportDaysLeft}d left` : 'Passport expiring'}
                </div>
              )}
              {/* Silence badge — only shown client-side after isMounted */}
              {silenceDays !== null && silenceDays > 14 && (
                <div
                  className={`mt-1 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full ${silenceDays > 30 ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}
                >
                  <BellOff className="w-2.5 h-2.5" />
                  Silent {silenceDays}d
                </div>
              )}
            </div>

            {/* Assigned team member avatar */}
            {assignedName && (
              <div className="shrink-0" title={`Assigned: ${assignedName}`}>
                {assignedAvatar ? (
                  <img
                    src={assignedAvatar}
                    alt={assignedName}
                    className="w-7 h-7 rounded-full object-cover ring-1 ring-[rgba(255,255,255,0.15)]"
                  />
                ) : (
                  <div className="w-7 h-7 rounded-full bg-[rgba(255,255,255,0.08)] ring-1 ring-[rgba(255,255,255,0.15)] flex items-center justify-center">
                    <span className="text-[9px] font-bold text-[var(--tx-secondary)] uppercase">
                      {assignedName.slice(0, 2)}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Strategic Peek Info (Always visible in card, but stylized) */}
          <div className="space-y-4">
            {/* Last Interaction Summary */}
            {client.last_interaction_summary ? (
              <div
                className={`p-2.5 rounded-[0.75rem] border border-[rgba(255,255,255,0.05)] text-[11px] ${badgeStyle} line-clamp-2`}
              >
                <div className="flex items-center gap-1.5 mb-1.5 opacity-80 uppercase tracking-widest text-[9px] font-bold">
                  <MessageCircle className="w-3 h-3" />
                  <span className="capitalize">{sentiment} Interaction</span>
                </div>
                <span className="leading-relaxed">
                  &quot;{client.last_interaction_summary}&quot;
                </span>
              </div>
            ) : (
              <div className="p-2.5 rounded-[0.75rem] border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] text-[var(--tx-secondary)] italic text-[11px]">
                No recent interactions
              </div>
            )}

            {/* Tags row */}
            {client.tags && client.tags.length > 0 && (
              <div className="flex items-center gap-1 flex-wrap">
                <Tag className="w-2.5 h-2.5 text-[var(--tx-tertiary)] shrink-0" />
                {client.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    className="px-1.5 py-0.5 rounded-full text-[9px] font-medium uppercase tracking-wide"
                    style={{
                      background: 'rgba(212,132,90,0.12)',
                      color: 'var(--bz-accent)',
                      border: '1px solid rgba(212,132,90,0.2)',
                    }}
                  >
                    {tag}
                  </span>
                ))}
                {client.tags.length > 3 && (
                  <span className="text-[9px] text-[var(--tx-tertiary)]">
                    +{client.tags.length - 3}
                  </span>
                )}
              </div>
            )}

            {/* Quick Stats Row */}
            <div className="flex items-center justify-between pt-3 border-t border-[var(--glass-rim)] text-[var(--tx-secondary)] font-mono text-[10px] uppercase tracking-wider">
              <div
                className="flex items-center gap-1.5"
                title={
                  client.last_interaction_date
                    ? new Date(client.last_interaction_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })
                    : 'No contact'
                }
              >
                <Clock className="w-3 h-3" />
                <span>
                  {client.last_interaction_date
                    ? isMounted
                      ? (() => {
                          const days = Math.floor(
                            (Date.now() -
                              new Date(client.last_interaction_date).getTime()) /
                              86400000
                          );
                          if (days === 0) return 'today';
                          if (days === 1) return '1d ago';
                          if (days >= 30) return `${Math.floor(days / 30)}mo ago`;
                          if (days >= 7) return `${Math.floor(days / 7)}w ago`;
                          return `${days}d ago`;
                        })()
                      : '...'
                    : 'Never'}
                </span>
              </div>

              {/* Status label */}
              <span
                className="px-1.5 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wide"
                style={{
                  background:
                    {
                      lead: 'rgba(59,130,246,0.15)',
                      active: 'rgba(16,185,129,0.15)',
                      completed: 'rgba(139,92,246,0.15)',
                      inactive: 'rgba(107,114,128,0.15)',
                      lost: 'rgba(239,68,68,0.15)',
                    }[client.status] || 'rgba(107,114,128,0.15)',
                  color:
                    {
                      lead: '#60a5fa',
                      active: '#34d399',
                      completed: '#a78bfa',
                      inactive: '#9ca3af',
                      lost: '#f87171',
                    }[client.status] || '#9ca3af',
                }}
              >
                {client.status}
              </span>

              {/* Active practices count */}
              {(client.active_practices ?? 0) > 0 && (
                <span
                  className="px-1.5 py-0.5 rounded-full text-[9px] font-semibold"
                  style={{
                    background: 'rgba(99,102,241,0.15)',
                    color: '#818cf8',
                  }}
                  title={`${client.active_practices ?? 0} active process${(client.active_practices ?? 0) > 1 ? 'es' : ''}`}
                >
                  {client.active_practices ?? 0}p
                </span>
              )}

              {/* Action Buttons (Visible on Hover) */}
              <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                {client.email && (
                  <a
                    href={`mailto:${client.email}`}
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-md hover:bg-[rgba(255,255,255,0.1)] hover:text-white transition-colors"
                    title={client.email}
                  >
                    <Mail className="w-3 h-3" />
                  </a>
                )}
                {client.phone && (
                  <a
                    href={`tel:${client.phone}`}
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-md hover:bg-[rgba(16,185,129,0.15)] hover:text-[var(--neon-emerald)] transition-colors"
                    title={client.phone}
                  >
                    <Phone className="w-3 h-3" />
                  </a>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/process/new?client_id=${client.id}`);
                  }}
                  className="p-1.5 rounded-md hover:bg-[rgba(99,102,241,0.20)] hover:text-[#818cf8] transition-colors"
                  title="New process for this client"
                  aria-label="New process for this client"
                >
                  <Plus className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        </motion.div>

        {/* "Strategic Peek" Hover Effect */}
        <div className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-52 opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-300 translate-y-2 group-hover:translate-y-0">
          <div className="bg-black/90 backdrop-blur-md text-white p-3 rounded-lg shadow-xl text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[var(--tx-secondary)]">Sentiment:</span>
              <span className="capitalize text-white font-medium">{sentiment}</span>
            </div>
            {client.last_interaction_date &&
              isMounted &&
              (() => {
                const days = Math.floor(
                  (Date.now() - new Date(client.last_interaction_date).getTime()) / 86400000
                );
                return (
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--tx-secondary)]">Last contact:</span>
                    <span
                      className={`font-medium ${days > 30 ? 'text-red-400' : days > 14 ? 'text-yellow-400' : 'text-green-400'}`}
                    >
                      {days === 0 ? 'Today' : `${days}d ago`}
                    </span>
                  </div>
                );
              })()}
            {(client.active_practices ?? 0) > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-[var(--tx-secondary)]">Active:</span>
                <span className="font-medium text-indigo-300">
                  {client.active_practices ?? 0} process
                  {(client.active_practices ?? 0) > 1 ? 'es' : ''}
                </span>
              </div>
            )}
            {passportAlert && (
              <div className="flex items-center justify-between">
                <span className="text-[var(--tx-secondary)]">Passport:</span>
                <span className={passportAlert === 'expired' ? 'text-red-400' : 'text-yellow-400'}>
                  {passportDaysLeft !== null && passportDaysLeft < 0 ? `⚠ Expired ${Math.abs(passportDaysLeft)}d ago` : passportDaysLeft !== null ? `⚠ ${passportDaysLeft}d left` : '⚠ Expiring'}
                </span>
              </div>
            )}
            <div className="absolute bottom-[-4px] left-1/2 -translate-x-1/2 w-2 h-2 bg-black/90 rotate-45"></div>
          </div>
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
      prevProps.client.id === nextProps.client.id &&
      prevProps.client.full_name === nextProps.client.full_name &&
      prevProps.client.status === nextProps.client.status &&
      prevProps.client.last_sentiment === nextProps.client.last_sentiment &&
      prevProps.client.last_interaction_date === nextProps.client.last_interaction_date &&
      prevProps.client.last_interaction_summary === nextProps.client.last_interaction_summary &&
      prevProps.client.assigned_to === nextProps.client.assigned_to &&
      prevProps.client.passport_expiry === nextProps.client.passport_expiry &&
      prevProps.client.active_practices === nextProps.client.active_practices &&
      prevProps.isDragging === nextProps.isDragging
    );
  }
);

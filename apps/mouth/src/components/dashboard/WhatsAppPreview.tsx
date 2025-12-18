'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronRight, MessageCircle, Bot, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface WhatsAppMessage {
  id: string;
  contactName: string;
  contactPhone?: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  hasAiSuggestion?: boolean;
  isNewLead?: boolean;
  practiceId?: number;
}

interface WhatsAppPreviewProps {
  messages: WhatsAppMessage[];
  isLoading?: boolean;
}

export function WhatsAppPreview({ messages, isLoading }: WhatsAppPreviewProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-40 bg-[var(--background-elevated)] rounded animate-pulse" />
          <div className="h-4 w-16 bg-[var(--background-elevated)] rounded animate-pulse" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 bg-[var(--background-elevated)]/50 rounded-lg animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  const unreadCount = messages.filter((m) => !m.isRead).length;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-[var(--foreground)]">
            WhatsApp Recenti
          </h2>
          {unreadCount > 0 && (
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-[var(--accent)] text-white">
              {unreadCount}
            </span>
          )}
        </div>
        <Link
          href="/whatsapp"
          className="text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors flex items-center gap-1"
        >
          Inbox
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Messages List */}
      <div className="space-y-2">
        {messages.length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="w-8 h-8 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
            <p className="text-sm text-[var(--foreground-muted)]">
              Nessun messaggio recente
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <Link
              key={msg.id}
              href="/whatsapp"
              className={cn(
                'block p-3 rounded-lg border transition-all',
                msg.isRead
                  ? 'border-[var(--border)] hover:border-[var(--border-hover)]'
                  : 'border-[var(--accent)]/30 bg-[var(--accent)]/5 hover:bg-[var(--accent)]/10'
              )}
            >
              <div className="flex items-start gap-3">
                {/* Status Indicator */}
                <div className="relative mt-0.5">
                  <span
                    className={cn(
                      'flex w-2 h-2 rounded-full',
                      msg.isRead ? 'bg-[var(--foreground-muted)]' : 'bg-[var(--success)]'
                    )}
                  />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-[var(--foreground)] truncate">
                      {msg.contactName}
                    </p>
                    <span className="text-xs text-[var(--foreground-muted)]">
                      {msg.timestamp}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--foreground-muted)] truncate mt-0.5">
                    {msg.message}
                  </p>

                  {/* Tags */}
                  <div className="flex items-center gap-2 mt-1.5">
                    {msg.practiceId && (
                      <span className="text-xs text-[var(--accent)] bg-[var(--accent)]/10 px-1.5 py-0.5 rounded">
                        #{msg.practiceId}
                      </span>
                    )}
                    {msg.hasAiSuggestion && (
                      <span className="text-xs text-[var(--success)] flex items-center gap-1">
                        <Bot className="w-3 h-3" />
                        AI
                      </span>
                    )}
                    {msg.isNewLead && (
                      <span className="text-xs text-[var(--warning)] flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" />
                        Nuovo lead
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}

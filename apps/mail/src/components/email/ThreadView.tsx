'use client';

import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Paperclip, Clock, Reply, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EmailDetail, EmailSummary } from '@/lib/email.types';

interface ThreadMessage {
  message_id: string;
  subject: string;
  from: { address: string; name?: string };
  to: { address: string; name?: string }[];
  date: string;
  snippet: string;
  is_read: boolean;
  has_attachments: boolean;
  // Full content only available when loaded
  html_content?: string;
  text_content?: string;
  attachments?: {
    attachment_id: string;
    filename: string;
    size: number;
    mime_type: string;
  }[];
}

interface ThreadViewProps {
  /** All emails in the current folder to group into threads */
  emails: EmailSummary[];
  /** The currently selected email's full content */
  selectedEmail: EmailDetail | null;
  /** Currently selected message id */
  selectedEmailId: string | null;
  /** Callback when a thread message is clicked */
  onSelectEmail: (messageId: string) => void;
  /** Callback to initiate reply */
  onReply?: () => void;
  /** Callback to download an attachment */
  onDownloadAttachment?: (attachmentId: string, filename: string) => void;
}

function formatDate(dateStr: string): string {
  const timestamp = Number(dateStr);
  const date =
    !isNaN(timestamp) && timestamp > 1_000_000_000_000 ? new Date(timestamp) : new Date(dateStr);
  if (isNaN(date.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
  }
  if (diffDays < 7) {
    return date.toLocaleDateString('it-IT', {
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  return date.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getInitial(from: { address: string; name?: string }): string {
  const str = from.name || from.address;
  return str[0]?.toUpperCase() ?? '?';
}

function stripHtml(html: string): string {
  if (!html) return '';
  if (typeof document === 'undefined')
    return html
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  const div = document.createElement('div');
  div.innerHTML = html;
  return (div.textContent || '').replace(/\s+/g, ' ').trim();
}

/** Group emails into threads by subject (normalized) */
function groupByThread(emails: EmailSummary[]): Map<string, EmailSummary[]> {
  const threads = new Map<string, EmailSummary[]>();
  for (const email of emails) {
    // Normalize subject: remove Re:, Fwd: prefixes
    const normalizedSubject = email.subject
      .replace(/^(re|fwd|fw|sv|vs):\s*/gi, '')
      .trim()
      .toLowerCase();
    const existing = threads.get(normalizedSubject) ?? [];
    existing.push(email);
    threads.set(normalizedSubject, existing);
  }
  return threads;
}

interface MessageRowProps {
  message: EmailSummary;
  isSelected: boolean;
  isExpanded: boolean;
  fullContent: EmailDetail | null;
  onToggle: () => void;
  onSelect: () => void;
  onReply?: () => void;
  onDownloadAttachment?: (attachmentId: string, filename: string) => void;
}

function MessageRow({
  message,
  isSelected,
  isExpanded,
  fullContent,
  onToggle,
  onSelect,
  onReply,
  onDownloadAttachment,
}: MessageRowProps) {
  const hasContent = isSelected && fullContent;

  return (
    <div
      className={cn(
        'border border-[var(--border)] rounded-lg overflow-hidden transition-all',
        isSelected
          ? 'border-[var(--accent)]/40 bg-[var(--background-secondary)]'
          : 'bg-[var(--background-elevated)] hover:border-[var(--border)]/80'
      )}
    >
      {/* Collapsed header — always visible */}
      <button
        type="button"
        onClick={() => {
          onSelect();
          onToggle();
        }}
        className="w-full flex items-start gap-3 p-4 text-left transition-colors hover:bg-[var(--background-secondary)]/50"
      >
        {/* Avatar */}
        <div className="w-9 h-9 rounded-full bg-[var(--accent)]/10 flex items-center justify-center shrink-0">
          <span className="text-sm font-semibold text-[var(--accent)]">
            {getInitial(message.from)}
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span
              className={cn(
                'text-sm truncate',
                !message.is_read
                  ? 'font-semibold text-[var(--foreground)]'
                  : 'font-medium text-[var(--foreground-muted)]'
              )}
            >
              {message.from.name || message.from.address}
            </span>
            <div className="flex items-center gap-2 shrink-0">
              {message.has_attachments && (
                <Paperclip
                  className="w-3.5 h-3.5 text-[var(--foreground-muted)]"
                  aria-label="Ha allegati"
                />
              )}
              <span className="text-xs text-[var(--foreground-muted)]">
                {formatDate(message.date)}
              </span>
              <span className="text-[var(--foreground-muted)]">
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
              </span>
            </div>
          </div>

          {!isExpanded && (
            <p className="text-xs text-[var(--foreground-muted)] truncate mt-0.5">
              {message.snippet}
            </p>
          )}
        </div>

        {!message.is_read && (
          <span
            className="shrink-0 mt-1.5 w-2 h-2 rounded-full bg-[var(--accent)]"
            aria-label="Non letto"
          />
        )}
      </button>

      {/* Expanded body */}
      {isExpanded && (
        <div className="border-t border-[var(--border)] px-4 pb-4">
          {/* To/Date metadata */}
          <div className="flex items-center gap-2 text-xs text-[var(--foreground-muted)] pt-3 pb-4">
            <Clock className="w-3.5 h-3.5 shrink-0" />
            <span>
              {new Date(
                !isNaN(Number(message.date)) && Number(message.date) > 1_000_000_000_000
                  ? Number(message.date)
                  : message.date
              ).toLocaleString('it-IT', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>

          {/* Body */}
          <div className="text-sm text-[var(--foreground)] leading-relaxed">
            {hasContent ? (
              fullContent.html_content ? (
                <div
                  className="prose prose-sm prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: fullContent.html_content }}
                />
              ) : (
                <pre className="whitespace-pre-wrap font-sans text-sm">
                  {fullContent.text_content || message.snippet}
                </pre>
              )
            ) : (
              <p className="text-[var(--foreground-muted)] italic">{message.snippet}</p>
            )}
          </div>

          {/* Attachments */}
          {hasContent && fullContent.attachments && fullContent.attachments.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[var(--border)]">
              <p className="text-xs font-medium text-[var(--foreground-muted)] mb-2 flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5" />
                {fullContent.attachments.length} Allegat
                {fullContent.attachments.length === 1 ? 'o' : 'i'}
              </p>
              <div className="flex flex-wrap gap-2">
                {fullContent.attachments.map((att) => (
                  <button
                    key={att.attachment_id}
                    type="button"
                    onClick={() => onDownloadAttachment?.(att.attachment_id, att.filename)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--background)] border border-[var(--border)] hover:border-[var(--accent)]/50 transition-colors"
                    aria-label={`Scarica ${att.filename}`}
                  >
                    <Download className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <div className="text-left">
                      <p className="text-xs text-[var(--foreground)] truncate max-w-[140px]">
                        {att.filename}
                      </p>
                      <p className="text-[10px] text-[var(--foreground-muted)]">
                        {formatFileSize(att.size)}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Quick reply action */}
          {isSelected && onReply && (
            <div className="mt-4 pt-3 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={onReply}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--foreground-muted)] border border-[var(--border)] hover:border-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
              >
                <Reply className="w-4 h-4" />
                Rispondi
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ThreadView({
  emails,
  selectedEmail,
  selectedEmailId,
  onSelectEmail,
  onReply,
  onDownloadAttachment,
}: ThreadViewProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    () => new Set(selectedEmailId ? [selectedEmailId] : [])
  );

  // Find the thread containing the selected email
  const currentThread = useMemo<EmailSummary[]>(() => {
    if (!selectedEmailId) return [];
    const selected = emails.find((e) => e.message_id === selectedEmailId);
    if (!selected) return [];

    const normalizedSubject = selected.subject
      .replace(/^(re|fwd|fw|sv|vs):\s*/gi, '')
      .trim()
      .toLowerCase();

    return emails
      .filter((e) => {
        const n = e.subject
          .replace(/^(re|fwd|fw|sv|vs):\s*/gi, '')
          .trim()
          .toLowerCase();
        return n === normalizedSubject;
      })
      .sort((a, b) => {
        const aTime =
          Number(a.date) > 1_000_000_000_000 ? Number(a.date) : new Date(a.date).getTime();
        const bTime =
          Number(b.date) > 1_000_000_000_000 ? Number(b.date) : new Date(b.date).getTime();
        return bTime - aTime; // most recent first
      });
  }, [emails, selectedEmailId]);

  // Auto-expand newly selected message
  React.useEffect(() => {
    if (selectedEmailId) {
      setExpandedIds((prev) => new Set([...prev, selectedEmailId]));
    }
  }, [selectedEmailId]);

  const toggleExpanded = (messageId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  };

  if (currentThread.length === 0) {
    return null;
  }

  // Only show thread view if there are multiple messages in the thread
  if (currentThread.length < 2) {
    return null;
  }

  return (
    <div className="border-t border-[var(--border)] bg-[var(--background)]">
      {/* Thread header */}
      <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[var(--foreground)]">Conversazione</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] font-medium">
            {currentThread.length} messaggi
          </span>
        </div>
        <button
          type="button"
          onClick={() => {
            // Toggle all: if any collapsed, expand all; else collapse all
            const allExpanded = currentThread.every((m) => expandedIds.has(m.message_id));
            if (allExpanded) {
              setExpandedIds(new Set());
            } else {
              setExpandedIds(new Set(currentThread.map((m) => m.message_id)));
            }
          }}
          className="text-xs text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
        >
          {currentThread.every((m) => expandedIds.has(m.message_id))
            ? 'Comprimi tutti'
            : 'Espandi tutti'}
        </button>
      </div>

      {/* Thread messages */}
      <div className="p-4 space-y-2 max-h-[60vh] overflow-y-auto">
        {currentThread.map((message) => (
          <MessageRow
            key={message.message_id}
            message={message}
            isSelected={message.message_id === selectedEmailId}
            isExpanded={expandedIds.has(message.message_id)}
            fullContent={message.message_id === selectedEmailId ? selectedEmail : null}
            onToggle={() => toggleExpanded(message.message_id)}
            onSelect={() => onSelectEmail(message.message_id)}
            onReply={message.message_id === selectedEmailId ? onReply : undefined}
            onDownloadAttachment={onDownloadAttachment}
          />
        ))}
      </div>
    </div>
  );
}

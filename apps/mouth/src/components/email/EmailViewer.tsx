'use client';

import React, { useState, useEffect } from 'react';
import DOMPurify from 'dompurify';
import {
  X,
  Reply,
  ReplyAll,
  Forward,
  Star,
  Trash2,
  Paperclip,
  Download,
  Clock,
  ChevronDown,
  MoreHorizontal,
  User,
  UserPlus,
  ExternalLink,
  Building2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import type { EmailDetail, EmailAttachment } from '@/lib/api/email/email.types';
import type { Client } from '@/lib/api/crm/crm.types';

interface EmailViewerProps {
  email: EmailDetail | null;
  onClose: () => void;
  onReply: () => void;
  onReplyAll: () => void;
  onForward: () => void;
  onToggleFlag: () => void;
  onDelete: () => void;
  onDownloadAttachment: (attachmentId: string, filename: string) => void;
  isLoading?: boolean;
  onAddToCRM?: (email: string, name: string) => void;
}

export function EmailViewer({
  email,
  onClose,
  onReply,
  onReplyAll,
  onForward,
  onToggleFlag,
  onDelete,
  onDownloadAttachment,
  isLoading,
  onAddToCRM,
}: EmailViewerProps) {
  const [showFullHeaders, setShowFullHeaders] = useState(false);
  const [senderClient, setSenderClient] = useState<Client | null>(null);
  const [isLoadingClient, setIsLoadingClient] = useState(false);
  const [clientLookupDone, setClientLookupDone] = useState(false);

  // Lookup client when email changes
  useEffect(() => {
    const lookupClient = async () => {
      if (!email?.from?.address) {
        setSenderClient(null);
        setClientLookupDone(false);
        return;
      }

      setIsLoadingClient(true);
      setClientLookupDone(false);
      try {
        const client = await api.crm.getClientByEmail(email.from.address);
        setSenderClient(client);
      } catch (error) {
        console.error('Failed to lookup client:', error);
        setSenderClient(null);
      } finally {
        setIsLoadingClient(false);
        setClientLookupDone(true);
      }
    };

    lookupClient();
  }, [email?.from?.address]);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col h-full bg-[var(--background)]">
        <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
          <div className="h-6 w-64 bg-[var(--background-elevated)] rounded animate-pulse" />
          <div className="h-8 w-8 bg-[var(--background-elevated)] rounded animate-pulse" />
        </div>
        <div className="flex-1 p-6 space-y-4">
          <div className="h-4 w-full bg-[var(--background-elevated)] rounded animate-pulse" />
          <div className="h-4 w-3/4 bg-[var(--background-elevated)] rounded animate-pulse" />
          <div className="h-4 w-1/2 bg-[var(--background-elevated)] rounded animate-pulse" />
        </div>
      </div>
    );
  }

  if (!email) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--background)]">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-[var(--background-elevated)] flex items-center justify-center">
            <Paperclip className="w-8 h-8 text-[var(--foreground-muted)]" />
          </div>
          <p className="text-sm text-[var(--foreground-muted)]">Select an email to view</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--background)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors md:hidden"
          >
            <X className="w-5 h-5" />
          </button>
          <h2 className="text-lg font-semibold text-[var(--foreground)] truncate max-w-md">
            {email.subject || '(No subject)'}
          </h2>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <button
            onClick={onReply}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
            title="Reply"
          >
            <Reply className="w-5 h-5" />
          </button>
          <button
            onClick={onReplyAll}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
            title="Reply All"
          >
            <ReplyAll className="w-5 h-5" />
          </button>
          <button
            onClick={onForward}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
            title="Forward"
          >
            <Forward className="w-5 h-5" />
          </button>
          <div className="w-px h-5 bg-[var(--border)] mx-1" />
          <button
            onClick={onToggleFlag}
            className={cn(
              'p-2 rounded-lg transition-colors',
              email.is_flagged
                ? 'text-[var(--warning)]'
                : 'text-[var(--foreground-muted)] hover:text-[var(--warning)]'
            )}
            title={email.is_flagged ? 'Remove star' : 'Star'}
          >
            <Star className={cn('w-5 h-5', email.is_flagged && 'fill-current')} />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
            title="Delete"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Email Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Sender Info */}
        <div className="p-4 border-b border-[var(--border)]">
          <div className="flex items-start gap-3">
            {/* Avatar */}
            <div className="w-10 h-10 rounded-full bg-[var(--accent)]/10 flex items-center justify-center flex-shrink-0">
              <span className="text-sm font-semibold text-[var(--accent)]">
                {(email.from.name || email.from.address)[0].toUpperCase()}
              </span>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-[var(--foreground)]">
                  {email.from.name || email.from.address}
                </span>
                <span className="text-sm text-[var(--foreground-muted)]">
                  &lt;{email.from.address}&gt;
                </span>
              </div>

              <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] mt-0.5">
                <span>to {email.to.map((t) => t.name || t.address).join(', ')}</span>
                {email.cc && email.cc.length > 0 && (
                  <span>, cc: {email.cc.map((c) => c.name || c.address).join(', ')}</span>
                )}
                <button
                  onClick={() => setShowFullHeaders(!showFullHeaders)}
                  className="p-0.5 hover:bg-[var(--background-elevated)] rounded"
                >
                  <ChevronDown
                    className={cn(
                      'w-4 h-4 transition-transform',
                      showFullHeaders && 'rotate-180'
                    )}
                  />
                </button>
              </div>

              {showFullHeaders && (
                <div className="mt-2 p-3 bg-[var(--background-elevated)] rounded-lg text-xs text-[var(--foreground-muted)] space-y-1">
                  <div>
                    <strong>From:</strong> {email.from.name} &lt;{email.from.address}&gt;
                  </div>
                  <div>
                    <strong>To:</strong> {email.to.map((t) => `${t.name || ''} <${t.address}>`).join(', ')}
                  </div>
                  {email.cc && email.cc.length > 0 && (
                    <div>
                      <strong>Cc:</strong> {email.cc.map((c) => `${c.name || ''} <${c.address}>`).join(', ')}
                    </div>
                  )}
                  <div>
                    <strong>Date:</strong> {new Date(email.date).toLocaleString()}
                  </div>
                </div>
              )}
            </div>

            {/* Date */}
            <div className="flex items-center gap-1 text-sm text-[var(--foreground-muted)] flex-shrink-0">
              <Clock className="w-4 h-4" />
              <span>{formatDate(email.date)}</span>
            </div>
          </div>
        </div>

        {/* CRM Client Badge */}
        {clientLookupDone && (
          <div className="px-4 py-2 border-b border-[var(--border)] bg-[var(--background-elevated)]/50">
            {isLoadingClient ? (
              <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
                <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
                <span>Checking CRM...</span>
              </div>
            ) : senderClient ? (
              <a
                href={`/clients/${senderClient.id}`}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--success)]/10 text-[var(--success)] hover:bg-[var(--success)]/20 transition-colors text-sm font-medium"
              >
                {senderClient.client_type === 'company' ? (
                  <Building2 className="w-4 h-4" />
                ) : (
                  <User className="w-4 h-4" />
                )}
                <span>Cliente: {senderClient.full_name}</span>
                <ExternalLink className="w-3 h-3 opacity-60" />
              </a>
            ) : (
              <button
                onClick={() => onAddToCRM?.(email.from.address, email.from.name || '')}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors text-sm font-medium"
              >
                <UserPlus className="w-4 h-4" />
                <span>Nuovo contatto - Aggiungi a CRM</span>
              </button>
            )}
          </div>
        )}

        {/* Attachments */}
        {email.attachments && email.attachments.length > 0 && (
          <div className="p-4 border-b border-[var(--border)]">
            <div className="flex items-center gap-2 mb-2">
              <Paperclip className="w-4 h-4 text-[var(--foreground-muted)]" />
              <span className="text-sm font-medium text-[var(--foreground)]">
                {email.attachments.length} Attachment{email.attachments.length > 1 ? 's' : ''}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {email.attachments.map((attachment) => (
                <button
                  key={attachment.attachment_id}
                  onClick={() => onDownloadAttachment(attachment.attachment_id, attachment.filename)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors',
                    'bg-[var(--background-elevated)] hover:bg-[var(--background-secondary)]',
                    'border border-[var(--border)]'
                  )}
                >
                  <FileIcon mimeType={attachment.mime_type} />
                  <div className="text-left">
                    <p className="text-sm text-[var(--foreground)] truncate max-w-[150px]">
                      {attachment.filename}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)]">
                      {formatFileSize(attachment.size)}
                    </p>
                  </div>
                  <Download className="w-4 h-4 text-[var(--foreground-muted)]" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Email Body */}
        <div className="p-4">
          {email.html_content ? (
            <div
              className="prose prose-sm prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(email.html_content) }}
            />
          ) : (
            <pre className="text-sm text-[var(--foreground)] whitespace-pre-wrap font-sans">
              {email.text_content}
            </pre>
          )}
        </div>
      </div>

      {/* Quick Reply */}
      <div className="p-4 border-t border-[var(--border)]">
        <button
          onClick={onReply}
          className={cn(
            'w-full py-2.5 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2',
            'border border-[var(--border)] hover:border-[var(--accent)]',
            'text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
          )}
        >
          <Reply className="w-4 h-4" />
          Reply
        </button>
      </div>
    </div>
  );
}

function FileIcon({ mimeType }: { mimeType: string }) {
  const isPdf = mimeType.includes('pdf');
  const isImage = mimeType.startsWith('image/');
  const isDoc = mimeType.includes('document') || mimeType.includes('word');

  return (
    <div
      className={cn(
        'w-8 h-8 rounded flex items-center justify-center text-xs font-bold',
        isPdf && 'bg-red-500/10 text-red-500',
        isImage && 'bg-blue-500/10 text-blue-500',
        isDoc && 'bg-blue-600/10 text-blue-600',
        !isPdf && !isImage && !isDoc && 'bg-gray-500/10 text-gray-500'
      )}
    >
      {isPdf ? 'PDF' : isImage ? 'IMG' : isDoc ? 'DOC' : 'FILE'}
    </div>
  );
}

function formatDate(dateStr: string): string {
  // Handle timestamp (milliseconds) from Zoho API or ISO string
  const timestamp = Number(dateStr);
  const date = !isNaN(timestamp) && timestamp > 1000000000000
    ? new Date(timestamp)  // Timestamp in milliseconds
    : new Date(dateStr);   // ISO string

  if (isNaN(date.getTime())) return '';

  return date.toLocaleString('it-IT', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sanitizeHtml(html: string): string {
  // Secure sanitization using DOMPurify
  // Removes XSS vectors: scripts, event handlers, javascript: URLs, data: URLs, etc.
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a', 'b', 'i', 'u', 'strong', 'em', 'p', 'br', 'div', 'span',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'table', 'thead', 'tbody', 'tr', 'td', 'th',
      'img', 'blockquote', 'pre', 'code', 'hr',
    ],
    ALLOWED_ATTR: [
      'href', 'src', 'alt', 'title', 'class', 'style',
      'width', 'height', 'align', 'valign', 'colspan', 'rowspan',
    ],
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
  });
}

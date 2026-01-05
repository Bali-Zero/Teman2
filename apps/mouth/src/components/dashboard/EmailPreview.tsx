'use client';

import React, { useState } from 'react';
import {
  Mail,
  MailOpen,
  Paperclip,
  Reply,
  Trash2,
  Check,
  Search,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EmailSummary } from '@/lib/api/email/email.types';

interface EmailPreviewProps {
  emails: EmailSummary[];
  isLoading?: boolean;
  onDelete: (emailIds: string[]) => void;
  onMarkRead: (emailIds: string[], isRead: boolean) => void;
  onReply: (emailId: string) => void;
  hasMore?: boolean;
  onLoadMore?: () => void;
}

export function EmailPreview({
  emails,
  isLoading,
  onDelete,
  onMarkRead,
  onReply,
  hasMore,
  onLoadMore,
}: EmailPreviewProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEmails = emails.filter(email =>
    email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
    email.from.address.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedCount = selectedIds.size;
  const allSelected = filteredEmails.length > 0 && selectedIds.size === filteredEmails.length;

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredEmails.map(e => e.message_id)));
    }
  };

  const handleToggleSelect = (emailId: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(emailId)) {
      newSelected.delete(emailId);
    } else {
      newSelected.add(emailId);
    }
    setSelectedIds(newSelected);
  };

  const handleDeleteSelected = () => {
    if (selectedCount > 0) {
      onDelete(Array.from(selectedIds));
      setSelectedIds(new Set());
    }
  };

  const handleMarkReadSelected = (isRead: boolean) => {
    if (selectedCount > 0) {
      onMarkRead(Array.from(selectedIds), isRead);
      setSelectedIds(new Set());
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    
    if (diffHours < 1) return 'Now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffHours < 48) return 'Yesterday';
    return date.toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="bg-[var(--background)] rounded-xl border border-[var(--border)] p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-[var(--foreground)]">Recent Emails</h3>
          <div className="animate-pulse bg-[var(--muted)] w-20 h-6 rounded"></div>
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="animate-pulse">
              <div className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border)]">
                <div className="w-4 h-4 bg-[var(--muted)] rounded mt-1"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-[var(--muted)] rounded w-3/4"></div>
                  <div className="h-3 bg-[var(--muted)] rounded w-1/2"></div>
                  <div className="h-3 bg-[var(--muted)] rounded w-full"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[var(--background)] rounded-xl border border-[var(--border)] p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Recent Emails</h3>
        <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
          <Mail className="w-4 h-4" />
          <span>{filteredEmails.length}</span>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
        <input
          type="text"
          placeholder="Search emails..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-[var(--background-elevated)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:border-transparent"
        />
      </div>

      {/* Bulk Actions */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-2 mb-4 p-2 bg-[var(--background-elevated)] rounded-lg">
          <span className="text-sm text-[var(--foreground)]">
            {selectedCount} selected
          </span>
          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={() => handleMarkReadSelected(true)}
              className="p-1.5 rounded text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
              title="Mark as read"
            >
              <MailOpen className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleMarkReadSelected(false)}
              className="p-1.5 rounded text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
              title="Mark as unread"
            >
              <Mail className="w-4 h-4" />
            </button>
            <button
              onClick={handleDeleteSelected}
              className="p-1.5 rounded text-red-500 hover:bg-red-500/10 transition-colors"
              title="Delete selected"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Email List */}
      {filteredEmails.length === 0 ? (
        <div className="text-center py-12">
          <Mail className="w-12 h-12 text-[var(--foreground-muted)] mx-auto mb-4" />
          <p className="text-[var(--foreground-muted)]">
            {searchQuery ? 'No emails found' : 'No recent emails'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredEmails.map((email) => (
            <div
              key={email.message_id}
              className={cn(
                'group flex items-start gap-3 p-3 rounded-lg border transition-all cursor-pointer',
                'hover:bg-[var(--background-elevated)] hover:border-[var(--border)]',
                selectedIds.has(email.message_id) && 'bg-[var(--accent)]/10 border-[var(--accent)]',
                !email.is_read && 'bg-[var(--background-elevated)]'
              )}
            >
              {/* Checkbox */}
              <button
                onClick={() => handleToggleSelect(email.message_id)}
                className={cn(
                  'w-4 h-4 rounded border-2 flex items-center justify-center transition-colors mt-0.5',
                  selectedIds.has(email.message_id)
                    ? 'bg-[var(--accent)] border-[var(--accent)]'
                    : 'border-[var(--border)] hover:border-[var(--accent)]'
                )}
              >
                {selectedIds.has(email.message_id) && (
                  <Check className="w-3 h-3 text-white" />
                )}
              </button>

              {/* Email Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn(
                        'text-sm font-medium truncate',
                        email.is_read ? 'text-[var(--foreground-muted)]' : 'text-[var(--foreground)]'
                      )}>
                        {email.from.name || email.from.address}
                      </span>
                      {!email.is_read && (
                        <span className="w-2 h-2 bg-[var(--accent)] rounded-full"></span>
                      )}
                    </div>
                    <p className={cn(
                      'text-sm truncate mb-1',
                      email.is_read ? 'text-[var(--foreground-muted)]' : 'text-[var(--foreground)] font-medium'
                    )}>
                      {email.subject}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)] truncate">
                      {email.snippet}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-xs text-[var(--foreground-muted)] whitespace-nowrap">
                      {formatDate(email.date)}
                    </span>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {email.has_attachments && (
                        <Paperclip className="w-3 h-3 text-[var(--foreground-muted)]" />
                      )}
                      <button
                        onClick={() => onReply(email.message_id)}
                        className="p-1 rounded text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
                        title="Reply"
                      >
                        <Reply className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Load More */}
          {hasMore && onLoadMore && (
            <div className="flex justify-center pt-4">
              <button
                onClick={onLoadMore}
                className="px-4 py-2 text-sm text-[var(--foreground)] bg-[var(--background-elevated)] border border-[var(--border)] rounded-lg hover:bg-[var(--muted)] transition-colors"
              >
                Load More
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

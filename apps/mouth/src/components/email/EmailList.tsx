'use client';

import React from 'react';
import {
  Star,
  Paperclip,
  Mail,
  MailOpen,
  Trash2,
  Check,
  Search,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EmailSummary } from '@/lib/api/email/email.types';

interface EmailListProps {
  emails: EmailSummary[];
  selectedEmailId: string | null;
  selectedIds: Set<string>;
  onSelectEmail: (emailId: string) => void;
  onToggleSelect: (emailId: string) => void;
  onSelectAll: (select: boolean) => void;
  onMarkRead: (emailIds: string[], isRead: boolean) => void;
  onToggleFlag: (emailId: string) => void;
  onDelete: (emailIds: string[]) => void;
  onSearch: (query: string) => void;
  searchQuery: string;
  isLoading?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void;
  onPreviousPage?: () => void;
  currentPage?: number;
  totalEmails?: number;
}

export function EmailList({
  emails,
  selectedEmailId,
  selectedIds,
  onSelectEmail,
  onToggleSelect,
  onSelectAll,
  onMarkRead,
  onToggleFlag,
  onDelete,
  onSearch,
  searchQuery,
  isLoading,
  hasMore,
  onLoadMore,
  onPreviousPage,
  currentPage = 1,
  totalEmails = 0,
}: EmailListProps) {
  const [localSearch, setLocalSearch] = React.useState(searchQuery);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(localSearch);
  };

  const allSelected = emails.length > 0 && selectedIds.size === emails.length;
  const someSelected = selectedIds.size > 0;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 p-3 border-b border-[var(--border)] bg-[var(--background-secondary)]">
        {/* Select All Checkbox */}
        <button
          onClick={() => onSelectAll(!allSelected)}
          className={cn(
            'w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
            allSelected
              ? 'bg-[var(--accent)] border-[var(--accent)]'
              : 'border-[var(--border)] hover:border-[var(--accent)]'
          )}
        >
          {allSelected && <Check className="w-3 h-3 text-white" />}
        </button>

        {/* Bulk Actions */}
        {someSelected && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => onMarkRead(Array.from(selectedIds), true)}
              className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
              title="Mark as read"
            >
              <MailOpen className="w-4 h-4" />
            </button>
            <button
              onClick={() => onMarkRead(Array.from(selectedIds), false)}
              className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
              title="Mark as unread"
            >
              <Mail className="w-4 h-4" />
            </button>
            <button
              onClick={() => onDelete(Array.from(selectedIds))}
              className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
              title="Delete"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="flex-1 ml-auto max-w-xs">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
            <input
              type="text"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              placeholder="Search emails..."
              className={cn(
                'w-full pl-9 pr-3 py-2 text-sm rounded-lg transition-colors',
                'bg-[var(--background-elevated)] border border-[var(--border)]',
                'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                'focus:outline-none focus:border-[var(--accent)]'
              )}
            />
          </div>
        </form>
      </div>

      {/* Email List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          // Loading skeleton
          <div className="p-2 space-y-1">
            {Array.from({ length: 10 }).map((_, i) => (
              <div
                key={i}
                className="h-16 bg-[var(--background-elevated)] rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : emails.length === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center h-full text-center p-6">
            <Mail className="w-12 h-12 text-[var(--foreground-muted)] opacity-50 mb-4" />
            <p className="text-sm text-[var(--foreground-muted)]">
              {searchQuery ? 'No emails match your search' : 'No emails in this folder'}
            </p>
          </div>
        ) : (
          // Email rows
          <div className="divide-y divide-[var(--border)]">
            {emails.map((email) => {
              const isSelected = selectedIds.has(email.message_id);
              const isActive = email.message_id === selectedEmailId;

              return (
                <div
                  key={email.message_id}
                  className={cn(
                    'flex items-start gap-3 px-3 py-3 cursor-pointer transition-colors',
                    isActive
                      ? 'bg-[var(--accent)]/10'
                      : !email.is_read
                      ? 'bg-[var(--background-secondary)]'
                      : 'hover:bg-[var(--background-elevated)]'
                  )}
                >
                  {/* Checkbox */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleSelect(email.message_id);
                    }}
                    className={cn(
                      'w-5 h-5 mt-0.5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors',
                      isSelected
                        ? 'bg-[var(--accent)] border-[var(--accent)]'
                        : 'border-[var(--border)] hover:border-[var(--accent)]'
                    )}
                  >
                    {isSelected && <Check className="w-3 h-3 text-white" />}
                  </button>

                  {/* Star */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFlag(email.message_id);
                    }}
                    className={cn(
                      'mt-0.5 flex-shrink-0 transition-colors',
                      email.is_flagged
                        ? 'text-[var(--warning)]'
                        : 'text-[var(--foreground-muted)] hover:text-[var(--warning)]'
                    )}
                  >
                    <Star className={cn('w-4 h-4', email.is_flagged && 'fill-current')} />
                  </button>

                  {/* Email Content */}
                  <div
                    onClick={() => onSelectEmail(email.message_id)}
                    className="flex-1 min-w-0"
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className={cn(
                          'text-sm truncate',
                          !email.is_read ? 'font-semibold text-[var(--foreground)]' : 'text-[var(--foreground)]'
                        )}
                      >
                        {email.from.name || email.from.address}
                      </span>
                      <span className="text-xs text-[var(--foreground-muted)] flex-shrink-0">
                        {formatDate(email.date)}
                      </span>
                    </div>
                    <p
                      className={cn(
                        'text-sm truncate mb-0.5',
                        !email.is_read ? 'font-medium text-[var(--foreground)]' : 'text-[var(--foreground-muted)]'
                      )}
                    >
                      {email.subject || '(No subject)'}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)] truncate">
                      {email.snippet}
                    </p>
                  </div>

                  {/* Indicators */}
                  <div className="flex items-center gap-1 flex-shrink-0 mt-0.5">
                    {email.has_attachments && (
                      <Paperclip className="w-4 h-4 text-[var(--foreground-muted)]" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalEmails > 0 && (
        <div className="flex items-center justify-between p-3 border-t border-[var(--border)] bg-[var(--background-secondary)]">
          <span className="text-xs text-[var(--foreground-muted)]">
            {emails.length > 0 ? (currentPage - 1) * 50 + 1 : 0} - {Math.min(currentPage * 50, totalEmails)} of {totalEmails} emails
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={onPreviousPage}
              disabled={currentPage === 1}
              className="p-1.5 rounded text-[var(--foreground-muted)] hover:text-[var(--foreground)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={onLoadMore}
              disabled={!hasMore}
              className="p-1.5 rounded text-[var(--foreground-muted)] hover:text-[var(--foreground)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
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

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const isThisYear = date.getFullYear() === now.getFullYear();

  if (isToday) {
    return date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
  } else if (isThisYear) {
    return date.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
  } else {
    return date.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
  }
}

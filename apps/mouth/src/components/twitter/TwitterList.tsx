'use client';

import React from 'react';
import { MessageCircle, Search, Filter, Check, Twitter, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TwitterConversation } from '@/lib/api/twitter/twitter.types';

interface TwitterListProps {
  conversations: TwitterConversation[];
  selectedUserId: string | null;
  selectedIds: Set<string>;
  onSelectConversation: (userId: string) => void;
  onToggleSelect: (userId: string) => void;
  onSelectAll: (select: boolean) => void;
  onSearch: (query: string) => void;
  searchQuery: string;
  isLoading?: boolean;
}

export function TwitterList({
  conversations,
  selectedUserId,
  selectedIds,
  onSelectConversation,
  onToggleSelect,
  onSelectAll,
  onSearch,
  searchQuery,
  isLoading,
}: TwitterListProps) {
  const [localSearch, setLocalSearch] = React.useState(searchQuery);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(localSearch);
  };

  const allSelected = conversations.length > 0 && selectedIds.size === conversations.length;

  const filteredConversations = conversations.filter((conv) => {
    if (!localSearch) return true;
    const query = localSearch.toLowerCase();
    return (
      conv.twitter_user_id.toLowerCase().includes(query) ||
      conv.username?.toLowerCase().includes(query) ||
      conv.client_name?.toLowerCase().includes(query) ||
      conv.last_message?.toLowerCase().includes(query)
    );
  });

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 p-3 border-b border-[var(--border)] bg-[var(--background-secondary)]">
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

        <form onSubmit={handleSearchSubmit} className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
            <input
              type="text"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              placeholder="Search conversations..."
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
            />
          </div>
        </form>

        <button
          className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
          title="Filters"
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-16 bg-[var(--background-elevated)] rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center">
            <MessageCircle className="w-12 h-12 text-[var(--foreground-muted)] mb-4 opacity-50" />
            <p className="text-sm text-[var(--foreground-muted)]">
              {localSearch ? 'No conversations found' : 'No Twitter/X conversations yet'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {filteredConversations.map((conv) => {
              const isSelected = selectedUserId === conv.twitter_user_id;
              const isChecked = selectedIds.has(conv.twitter_user_id);

              return (
                <div
                  key={conv.twitter_user_id}
                  onClick={() => onSelectConversation(conv.twitter_user_id)}
                  className={cn(
                    'flex items-center gap-3 p-3 cursor-pointer transition-colors',
                    isSelected
                      ? 'bg-[var(--accent)]/10 border-l-2 border-[var(--accent)]'
                      : 'hover:bg-[var(--background-elevated)]'
                  )}
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleSelect(conv.twitter_user_id);
                    }}
                    className={cn(
                      'w-5 h-5 rounded border-2 flex items-center justify-center transition-colors flex-shrink-0',
                      isChecked
                        ? 'bg-[var(--accent)] border-[var(--accent)]'
                        : 'border-[var(--border)] hover:border-[var(--accent)]'
                    )}
                  >
                    {isChecked && <Check className="w-3 h-3 text-white" />}
                  </button>

                  <div className="w-12 h-12 rounded-full bg-black/20 flex items-center justify-center flex-shrink-0">
                    {conv.client_name ? (
                      <User className="w-6 h-6 text-black dark:text-white" />
                    ) : (
                      <Twitter className="w-6 h-6 text-black dark:text-white" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="text-sm font-semibold text-[var(--foreground)] truncate">
                        {conv.client_name || conv.username || `@${conv.twitter_user_id}`}
                      </h3>
                      <span className="text-xs text-[var(--foreground-muted)] flex-shrink-0 ml-2">
                        {formatTime(conv.last_message_date)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-[var(--foreground-muted)] truncate flex-1">
                        {conv.last_message || 'No messages'}
                      </p>
                      {conv.unread_count && conv.unread_count > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-black dark:bg-white text-white dark:text-black text-xs font-semibold flex-shrink-0">
                          {conv.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

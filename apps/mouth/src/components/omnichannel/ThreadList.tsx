'use client';

import { useCallback, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  CHANNEL_COLORS,
  CHANNEL_LABELS,
  type Thread,
  type ThreadFilter,
} from '@/lib/api/omnichannel/omnichannel.types';

interface ThreadListProps {
  threads: Thread[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onFilterChange: (filter: Partial<ThreadFilter>) => void;
  currentUserEmail?: string;
}

const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'bg-red-500',
  high: 'bg-orange-500',
  normal: 'bg-blue-500',
  low: 'bg-gray-400',
};

type TabValue = 'all' | 'my' | 'unassigned' | 'vip';

export function ThreadList({
  threads,
  selectedId,
  onSelect,
  onFilterChange,
  currentUserEmail,
}: ThreadListProps) {
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<TabValue>('all');

  const handleTabChange = useCallback(
    (tab: string) => {
      const value = tab as TabValue;
      setActiveTab(value);
      switch (value) {
        case 'my':
          onFilterChange({ assigned_to: currentUserEmail, status: undefined });
          break;
        case 'unassigned':
          onFilterChange({ assigned_to: '__unassigned__', status: 'open' });
          break;
        case 'vip':
          onFilterChange({ priority: 'urgent', status: undefined });
          break;
        default:
          onFilterChange({ assigned_to: undefined, status: undefined, priority: undefined });
      }
    },
    [onFilterChange, currentUserEmail]
  );

  const handleSearch = useCallback(
    (value: string) => {
      setSearch(value);
      onFilterChange({ search: value || undefined });
    },
    [onFilterChange]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border)]">
        <h2 className="text-lg font-bold text-[var(--foreground)]">Inbox</h2>
        <p className="text-xs text-[var(--foreground-muted)]">{threads.length} conversations</p>
      </div>

      {/* Tabs */}
      <div className="px-3 pt-3">
        <Tabs defaultValue="all" value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="w-full grid grid-cols-4 h-8">
            <TabsTrigger value="all" className="text-xs">
              All
            </TabsTrigger>
            <TabsTrigger value="my" className="text-xs">
              My
            </TabsTrigger>
            <TabsTrigger value="unassigned" className="text-xs">
              Open
            </TabsTrigger>
            <TabsTrigger value="vip" className="text-xs">
              VIP
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <Input
          placeholder="Search conversations..."
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="h-8 text-sm bg-[var(--background-secondary)]"
        />
      </div>

      {/* Thread List */}
      <ScrollArea className="flex-1">
        <div className="divide-y divide-[var(--border)]">
          {threads.map((thread) => (
            <ThreadItem
              key={thread.id}
              thread={thread}
              isSelected={thread.id === selectedId}
              onClick={() => onSelect(thread.id)}
            />
          ))}
          {threads.length === 0 && (
            <div className="p-8 text-center text-[var(--foreground-muted)] text-sm">
              No conversations found
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function ThreadItem({
  thread,
  isSelected,
  onClick,
}: {
  thread: Thread;
  isSelected: boolean;
  onClick: () => void;
}) {
  const timeAgo = thread.last_activity_at ? formatTimeAgo(new Date(thread.last_activity_at)) : '';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-4 py-3 hover:bg-[var(--background-secondary)] transition-colors ${
        isSelected ? 'bg-[var(--background-secondary)] border-l-2 border-[var(--accent)]' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* Client name + Priority dot */}
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                PRIORITY_COLORS[thread.priority] || PRIORITY_COLORS.normal
              }`}
            />
            <span className="font-medium text-sm text-[var(--foreground)] truncate">
              {thread.client_name || thread.subject || 'Unknown'}
            </span>
          </div>

          {/* Preview */}
          <p className="text-xs text-[var(--foreground-muted)] mt-1 truncate">
            {thread.last_message_preview || 'No messages'}
          </p>

          {/* Channel badges */}
          <div className="flex items-center gap-1 mt-1.5">
            {thread.channels.map((ch) => (
              <span
                key={ch}
                className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                style={{
                  backgroundColor: `${CHANNEL_COLORS[ch] || '#6B7280'}20`,
                  color: CHANNEL_COLORS[ch] || '#6B7280',
                }}
              >
                {CHANNEL_LABELS[ch] || ch}
              </span>
            ))}
            {thread.intent && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--background-elevated)] text-[var(--foreground-muted)]">
                {thread.intent}
              </span>
            )}
          </div>
        </div>

        {/* Right side: time + unread */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="text-[10px] text-[var(--foreground-muted)]">{timeAgo}</span>
          {thread.unread_count > 0 && (
            <Badge
              variant="default"
              className="h-5 min-w-5 text-[10px] bg-[var(--accent)] text-white"
            >
              {thread.unread_count}
            </Badge>
          )}
        </div>
      </div>
    </button>
  );
}

function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `${diffMins}m`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d`;
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

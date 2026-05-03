'use client';

import { useCallback, useEffect, useState } from 'react';
import { ThreadList } from '@/components/omnichannel/ThreadList';
import { ThreadView } from '@/components/omnichannel/ThreadView';
import { CRMPanel } from '@/components/omnichannel/CRMPanel';
import type {
  CRMContext,
  Thread,
  ThreadFilter,
  ThreadMessage,
} from '@/lib/api/omnichannel/omnichannel.types';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';

export default function OmnichannelPage() {
  // Thread list state
  const [threads, setThreads] = useState<Thread[]>([]);
  const [totalThreads, setTotalThreads] = useState(0);
  const [filters, setFilters] = useState<ThreadFilter>({ limit: 50, offset: 0 });
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);

  // Selected thread state
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // CRM context
  const [crmContext, setCrmContext] = useState<CRMContext | null>(null);
  const [isLoadingContext, setIsLoadingContext] = useState(false);

  // Panel visibility
  const [showCRM, setShowCRM] = useState(true);

  // Current user
  const userProfile = api.getUserProfile();
  const currentUserEmail = userProfile?.email || '';

  // Fetch threads
  const fetchThreads = useCallback(async () => {
    setIsLoadingThreads(true);
    try {
      const data = await api.request<{
        threads: Thread[];
        total: number;
      }>(`/api/omnichannel/threads?${buildQueryString(filters)}`);
      setThreads(data.threads);
      setTotalThreads(data.total);
    } catch (err) {
      logger.error('Failed to fetch threads', {}, err as Error);
    } finally {
      setIsLoadingThreads(false);
    }
  }, [filters]);

  // Fetch thread detail
  const fetchThread = useCallback(async (threadId: string) => {
    setIsLoadingMessages(true);
    try {
      const data = await api.request<{
        thread: Thread;
        messages: ThreadMessage[];
      }>(`/api/omnichannel/threads/${threadId}?message_limit=100`);
      setSelectedThread(data.thread);
      setMessages(data.messages);
    } catch (err) {
      logger.error('Failed to fetch thread', {}, err as Error);
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  // Fetch CRM context
  const fetchContext = useCallback(async (threadId: string) => {
    setIsLoadingContext(true);
    try {
      const data = await api.request<CRMContext>(`/api/omnichannel/threads/${threadId}/context`);
      setCrmContext(data);
    } catch (err) {
      logger.error('Failed to fetch context', {}, err as Error);
    } finally {
      setIsLoadingContext(false);
    }
  }, []);

  // Load threads on mount and filter change
  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  // Load thread detail on selection
  useEffect(() => {
    if (selectedId) {
      fetchThread(selectedId);
      fetchContext(selectedId);
    }
  }, [selectedId, fetchThread, fetchContext]);

  // Handlers
  const handleFilterChange = useCallback((partial: Partial<ThreadFilter>) => {
    setFilters((prev) => ({ ...prev, ...partial, offset: 0 }));
  }, []);

  const handleSendMessage = useCallback(
    async (content: string, opts: { channel?: string; isNote?: boolean }) => {
      if (!selectedId) return;
      try {
        await api.request(`/api/omnichannel/threads/${selectedId}/messages`, {
          method: 'POST',
          body: JSON.stringify({
            content,
            channel: opts.channel,
            is_internal_note: opts.isNote ?? false,
          }),
        });
        // Refresh messages
        await fetchThread(selectedId);
        // Refresh thread list (preview/activity changed)
        await fetchThreads();
      } catch (err) {
        logger.error('Failed to send message', {}, err as Error);
      }
    },
    [selectedId, fetchThread, fetchThreads]
  );

  const handleUpdateThread = useCallback(
    async (update: { status?: string; priority?: string }) => {
      if (!selectedId) return;
      try {
        await api.request(`/api/omnichannel/threads/${selectedId}`, {
          method: 'PATCH',
          body: JSON.stringify(update),
        });
        await fetchThread(selectedId);
        await fetchThreads();
      } catch (err) {
        logger.error('Failed to update thread', {}, err as Error);
      }
    },
    [selectedId, fetchThread, fetchThreads]
  );

  const handleAssign = useCallback(
    async (email: string) => {
      if (!selectedId) return;
      try {
        await api.request(`/api/omnichannel/threads/${selectedId}/assign`, {
          method: 'POST',
          body: JSON.stringify({ assignee: email }),
        });
        await fetchThread(selectedId);
        await fetchThreads();
      } catch (err) {
        logger.error('Failed to assign thread', {}, err as Error);
      }
    },
    [selectedId, fetchThread, fetchThreads]
  );

  return (
    <div className="h-[calc(100vh-8rem)] -m-4 md:-m-6 lg:-m-8 flex">
      {/* Pane A: Thread List */}
      <div className="w-96 border-r border-[var(--border)] bg-[var(--background)] flex flex-col flex-shrink-0">
        <ThreadList
          threads={threads}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onFilterChange={handleFilterChange}
          currentUserEmail={currentUserEmail}
        />
      </div>

      {/* Pane B: Thread View */}
      <div className="flex-1 flex flex-col min-w-0">
        {isLoadingMessages && selectedId ? (
          <div className="flex-1 flex items-center justify-center text-[var(--foreground-muted)]">
            Loading...
          </div>
        ) : (
          <ThreadView
            thread={selectedThread}
            messages={messages}
            onSendMessage={handleSendMessage}
            onUpdateThread={handleUpdateThread}
          />
        )}
      </div>

      {/* Pane C: CRM Panel (collapsible) */}
      {showCRM && (
        <div className="w-80 border-l border-[var(--border)] bg-[var(--background)] flex-shrink-0 hidden xl:flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
            <h4 className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider">
              Intelligence
            </h4>
            <button
              type="button"
              onClick={() => setShowCRM(false)}
              className="text-xs text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
            >
              Hide
            </button>
          </div>
          <CRMPanel
            thread={selectedThread}
            context={crmContext}
            isLoading={isLoadingContext}
            onAssign={handleAssign}
          />
        </div>
      )}

      {/* Show CRM toggle (when hidden) */}
      {!showCRM && (
        <button
          type="button"
          onClick={() => setShowCRM(true)}
          className="absolute right-2 top-2 text-xs px-2 py-1 rounded bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)] hidden xl:block"
        >
          Show Panel
        </button>
      )}
    </div>
  );
}

function buildQueryString(filters: ThreadFilter): string {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.priority) params.set('priority', filters.priority);
  if (filters.assigned_to) params.set('assigned_to', filters.assigned_to);
  if (filters.channel) params.set('channel', filters.channel);
  if (filters.search) params.set('search', filters.search);
  params.set('limit', String(filters.limit ?? 50));
  params.set('offset', String(filters.offset ?? 0));
  return params.toString();
}

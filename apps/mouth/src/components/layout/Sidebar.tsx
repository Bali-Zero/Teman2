import React from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Plus, X, Loader2, History, MessageSquare, Trash2, Activity } from 'lucide-react';
import { Conversation } from '@/types';
import { ComplianceWidget } from '../dashboard/ComplianceWidget';
import { ComplianceAlert } from '@/types/compliance';

const MOCK_ALERTS: ComplianceAlert[] = [
  {
    alert_id: 'alert-1',
    compliance_item_id: 'item-1',
    client_id: 'current-user',
    severity: 'urgent',
    title: 'URGENT: KITAS Expiry',
    message: 'Your Investor KITAS expires in 25 days. Please start the renewal process immediately to avoid penalties.',
    deadline: new Date(Date.now() + 25 * 24 * 60 * 60 * 1000).toISOString(),
    days_until_deadline: 25,
    action_required: 'Contact agent',
    status: 'pending',
    created_at: new Date().toISOString()
  },
  {
    alert_id: 'alert-2',
    compliance_item_id: 'item-2',
    client_id: 'current-user',
    severity: 'warning',
    title: 'WARNING: Tax Deadline',
    message: 'Monthly VAT (PPn) filing for the previous month is due in 5 days.',
    deadline: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    days_until_deadline: 5,
    action_required: 'File taxes',
    status: 'pending',
    created_at: new Date().toISOString()
  }
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  isLoading: boolean;
  isConversationsLoading: boolean;
  conversations: Conversation[];
  currentConversationId: number | null;
  onConversationClick: (id: number) => void;
  onDeleteConversation: (id: number) => void;
  clockError: string | null;
  onClearHistory: () => void;
}

export function Sidebar({
  isOpen,
  onClose,
  onNewChat,
  isLoading,
  isConversationsLoading,
  conversations,
  currentConversationId,
  onConversationClick,
  onDeleteConversation,
  clockError,
  onClearHistory,
}: SidebarProps) {
  const router = useRouter();

  return (
    <>
      {/* Sidebar Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        fixed z-50 left-0 top-0
        w-72 h-full
        transition-transform duration-300 ease-in-out
        bg-black/60 backdrop-blur-xl flex flex-col
        shadow-2xl border-r border-white/10
      `}
      >
        {/* Close Button */}
        <div className="absolute top-3 right-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close sidebar"
            className="hover:bg-white/10"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Sidebar Header */}
        <div className="p-4 border-b border-[var(--border)]/50 space-y-2">
          <Button
            onClick={onNewChat}
            className="w-full justify-start gap-2 shadow-sm hover:shadow-md transition-all bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
            variant="default"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </Button>
          <Button
            onClick={() => router.push('/agents')}
            className="w-full justify-start gap-2 shadow-sm hover:shadow-md transition-all bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)] border border-[var(--border)]"
            variant="outline"
          >
            <Activity className="w-4 h-4" />
            Agents Dashboard
          </Button>
        </div>

        {/* Compliance Alerts Widget */}
        <div className="px-4 pt-2 -mb-2 flex justify-end">
           <ComplianceWidget alerts={MOCK_ALERTS} />
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-white/10">
          {isLoading || isConversationsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--foreground-muted)]" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8">
              <History className="w-8 h-8 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">No conversations yet</p>
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`group relative p-2 rounded-lg cursor-pointer transition-all ${
                    currentConversationId === conv.id
                      ? 'bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/20'
                      : 'hover:bg-white/5 text-[var(--foreground)] border border-transparent'
                  }`}
                  onClick={() => onConversationClick(conv.id)}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare
                      className={`w-4 h-4 mt-0.5 flex-shrink-0 ${currentConversationId === conv.id ? 'text-[var(--accent)]' : 'text-[var(--foreground-muted)]'}`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{conv.title}</p>
                      <p
                        className={`text-xs truncate ${
                          currentConversationId === conv.id
                            ? 'text-[var(--accent)]/70'
                            : 'text-[var(--foreground-muted)]'
                        }`}
                      >
                        {conv.preview || `${conv.message_count} messages`}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(conv.id);
                    }}
                    className={`absolute right-2 top-2 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${
                      currentConversationId === conv.id
                        ? 'hover:bg-[var(--accent)]/20 text-[var(--accent)]'
                        : 'hover:bg-white/10 text-[var(--foreground-muted)]'
                    }`}
                    aria-label="Delete conversation"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[var(--border)]/50 space-y-2 bg-[var(--background-secondary)]/50">
          {clockError && (
            <div className="p-2 rounded-md bg-[var(--error)]/10 border border-[var(--error)]/20">
              <p className="text-xs text-[var(--error)]">{clockError}</p>
            </div>
          )}
          {conversations.length > 0 && (
            <Button
              onClick={onClearHistory}
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2 text-[var(--foreground-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/10"
            >
              <Trash2 className="w-4 h-4" />
              Clear History
            </Button>
          )}
        </div>
      </aside>
    </>
  );
}

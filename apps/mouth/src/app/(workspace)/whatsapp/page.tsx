'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { WhatsAppList, WhatsAppViewer } from '@/components/whatsapp';
import type { WhatsAppConversation, WhatsAppMessage } from '@/lib/api/whatsapp/whatsapp.types';
import type { Client } from '@/lib/api/crm/crm.types';

export default function WhatsAppPage() {
  // Conversations state
  const [conversations, setConversations] = useState<WhatsAppConversation[]>([]);
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);

  // Messages state
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [client, setClient] = useState<Client | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');

  // Load conversations
  const loadConversations = useCallback(async () => {
    setIsLoadingConversations(true);
    try {
      const convs = await api.whatsapp.getConversations({ limit: 50 });
      setConversations(convs);
    } catch (error) {
      logger.error('Failed to load WhatsApp conversations:', {}, error as Error);
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  // Load messages for selected phone
  const loadMessages = useCallback(
    async (phone: string) => {
      setIsLoadingMessages(true);
      try {
        const msgs = await api.whatsapp.getMessages(phone, 100);
        setMessages(msgs);
        // ... (client load logic)
      } catch (error) {
        logger.error('Failed to load WhatsApp messages:', {}, error as Error);
      } finally {
        setIsLoadingMessages(false);
      }
    },
    [conversations]
  );

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Load messages when phone is selected
  useEffect(() => {
    if (selectedPhone) {
      loadMessages(selectedPhone);
    } else {
      setMessages([]);
      setClient(null);
    }
  }, [selectedPhone, loadMessages]);

  // Handle conversation selection
  const handleSelectConversation = (phone: string) => {
    setSelectedPhone(phone);
  };

  // Handle toggle select
  const handleToggleSelect = (phone: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(phone)) {
        next.delete(phone);
      } else {
        next.add(phone);
      }
      return next;
    });
  };

  // Handle select all
  const handleSelectAll = (select: boolean) => {
    if (select) {
      setSelectedIds(new Set(conversations.map((c) => c.phone)));
    } else {
      setSelectedIds(new Set());
    }
  };

  // Handle send message
  const handleSendMessage = useCallback(
    async (text: string, replyToMessageId?: string) => {
      if (!selectedPhone) return;

      try {
        await api.whatsapp.sendMessage(selectedPhone, text, replyToMessageId);
        // Reload messages after sending
        await loadMessages(selectedPhone);
        // Reload conversations to update last message
        await loadConversations();
      } catch (error) {
        logger.error('Failed to send message:', {}, error as Error);
        throw error;
      }
    },
    [selectedPhone, loadMessages, loadConversations]
  );

  // Handle search
  const handleSearch = (query: string) => {
    setSearchQuery(query);
  };

  return (
    <div className="h-[calc(100vh-8rem)] -m-4 md:-m-6 lg:-m-8 flex">
      {/* Conversations List */}
      <div className="w-96 border-r border-[var(--border)] bg-[var(--background)] flex flex-col">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 border-b border-[var(--border)]">
          <div>
            <h1 className="text-xl font-bold text-[var(--foreground)]">WhatsApp Business</h1>
            <p className="text-sm text-[var(--foreground-muted)]">
              {conversations.length} conversations
            </p>
          </div>
          <Button
            className="gap-2"
            size="sm"
            onClick={() => toast.info('Coming soon', { description: 'Starting new WhatsApp chats from the dashboard will be available in a future update.' })}
          >
            <Plus className="w-4 h-4" />
            New Chat
          </Button>
        </div>

        {/* List */}
        <WhatsAppList
          conversations={conversations}
          selectedPhone={selectedPhone}
          selectedIds={selectedIds}
          onSelectConversation={handleSelectConversation}
          onToggleSelect={handleToggleSelect}
          onSelectAll={handleSelectAll}
          onSearch={handleSearch}
          searchQuery={searchQuery}
          isLoading={isLoadingConversations}
        />
      </div>

      {/* Messages Viewer */}
      <div className="flex-1 flex flex-col">
        <WhatsAppViewer
          phone={selectedPhone}
          messages={messages}
          client={client}
          onClose={() => setSelectedPhone(null)}
          onSendMessage={handleSendMessage}
          isLoading={isLoadingMessages}
        />
      </div>
    </div>
  );
}

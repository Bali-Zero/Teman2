'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { InboxSidebar } from './components/InboxSidebar';
import { ChatArea } from './components/ChatArea';
import { LeadContextPanel } from './components/LeadContextPanel';
import { EnrichedConversation, Message, ChannelType } from './types';
import { useToast } from '@/components/ui/use-toast';

export default function OmnichannelPage() {
  const [conversations, setConversations] = useState<EnrichedConversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const selectedConversation = conversations.find(c => c.id === selectedId) || null;

  // Fetch conversations from ALL channels
  const fetchConversations = async () => {
    try {
      setLoading(true);
      // Fetch WhatsApp (Real API)
      const waData = await api.whatsapp.getConversations();
      
      // Try fetch Telegram/Instagram (Real API if available, else empty)
      // Note: We'll wrap these in try-catch to not block the main UI if they fail
      let tgData = [];
      let igData = [];
      try {
        // Assume endpoints exist or handle gracefully
        // tgData = await api.request('/api/telegram/conversations'); 
      } catch (e) {}

      // Transform & Enrich Data for the new UI
      const enriched: EnrichedConversation[] = [
        ...waData.map(c => ({
          ...c,
          channel: 'whatsapp' as ChannelType,
          status: 'open',
          priority: 'medium',
          tags: ['#New'],
          unreadCount: 0,
          client_name: c.client_name || c.phone, // Fallback
        }))
        // Add TG/IG mapping here when available
      ];

      setConversations(enriched);
    } catch (error) {
      logger.error('Failed to fetch conversations', { error });
      toast({ title: "Error", description: "Could not load inbox", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  // Fetch messages when a conversation is selected
  useEffect(() => {
    if (!selectedId || !selectedConversation) return;

    const fetchMessages = async () => {
      try {
        let msgs: any[] = [];
        if (selectedConversation.channel === 'whatsapp') {
          msgs = await api.whatsapp.getMessages(selectedConversation.phone);
        }
        
        // Transform to UI Message type
        const uiMessages: Message[] = msgs.map((m: any) => ({
          id: m.id || Math.random().toString(),
          text: m.message_text || m.content || "",
          sender: m.direction === 'outbound' ? 'agent' : 'user',
          timestamp: m.timestamp || new Date().toISOString(),
          isInternalNote: false // Backend doesn't support this yet, defaulting to false
        }));

        // Sort by time
        setMessages(uiMessages.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()));
      } catch (error) {
        logger.error('Failed to fetch messages', { error });
      }
    };

    fetchMessages();
  }, [selectedId, selectedConversation]);

  // Initial Load
  useEffect(() => {
    fetchConversations();
  }, []);

  const handleSendMessage = async (text: string, isNote: boolean) => {
    if (!selectedConversation) return;

    // Optimistic UI Update
    const newMessage: Message = {
      id: Date.now().toString(),
      text: text,
      sender: 'agent',
      timestamp: new Date().toISOString(),
      isInternalNote: isNote
    };
    setMessages(prev => [...prev, newMessage]);

    try {
      if (isNote) {
        // TODO: Call Internal Note API (Phase 2)
        toast({ title: "Note Added", description: "Internal note saved (Mock)" });
      } else {
        if (selectedConversation.channel === 'whatsapp') {
          await api.whatsapp.sendMessage(selectedConversation.phone, text);
        }
      }
    } catch (error) {
      toast({ title: "Error", description: "Failed to send message", variant: "destructive" });
    }
  };

  return (
    <div className="flex h-full w-full bg-background">
      {/* Pane 1: Inbox */}
      <InboxSidebar 
        conversations={conversations} 
        selectedId={selectedId} 
        onSelect={setSelectedId}
        isLoading={loading}
      />

      {/* Pane 2: Action Stream */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatArea 
          conversation={selectedConversation} 
          messages={messages}
          onSendMessage={handleSendMessage}
        />
      </div>

      {/* Pane 3: Intelligence Panel */}
      <LeadContextPanel conversation={selectedConversation} />
    </div>
  );
}
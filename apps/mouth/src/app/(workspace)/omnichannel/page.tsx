'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { InboxSidebar } from './components/InboxSidebar';
import { ChatArea } from './components/ChatArea';
import { LeadContextPanel } from './components/LeadContextPanel';
import { EnrichedConversation, Message, ChannelType, ConversationStatus } from './types';

export default function OmnichannelPage() {
  const [conversations, setConversations] = useState<EnrichedConversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);

  const selectedConversation = conversations.find(c => c.id === selectedId) || null;

  // Fetch conversations from ALL channels
  const fetchConversations = async () => {
    try {
      setLoading(true);
      // Fetch WhatsApp (Real API)
      const waData = await api.whatsapp.getConversations();
      
      // Transform & Enrich Data for the new UI
      const enriched: EnrichedConversation[] = waData.map(c => ({
        id: c.id,
        phone: c.phone,
        client_name: c.client_name || c.phone,
        last_message: c.last_message || "",
        last_message_date: c.last_message_date,
        channel: 'whatsapp' as ChannelType,
        status: 'open' as ConversationStatus,
        priority: 'medium',
        tags: ['#New'],
        unreadCount: c.unread_count || 0,
      }));

      setConversations(enriched);
    } catch (error) {
      logger.error('Failed to fetch conversations');
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
          isInternalNote: false 
        }));

        setMessages(uiMessages.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()));
      } catch (error) {
        logger.error('Failed to fetch messages');
      }
    };

    fetchMessages();
  }, [selectedId, selectedConversation]);

  useEffect(() => {
    fetchConversations();
  }, []);

  const handleSendMessage = async (text: string, isNote: boolean) => {
    if (!selectedConversation) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      text: text,
      sender: 'agent',
      timestamp: new Date().toISOString(),
      isInternalNote: isNote
    };
    setMessages(prev => [...prev, newMessage]);

    try {
      if (!isNote) {
        if (selectedConversation.channel === 'whatsapp') {
          await api.whatsapp.sendMessage(selectedConversation.phone, text);
        }
      }
    } catch (error) {
      logger.error('Failed to send message');
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
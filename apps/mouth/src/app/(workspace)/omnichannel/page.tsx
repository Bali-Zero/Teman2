'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { InboxSidebar } from './components/InboxSidebar';
import { ChatArea } from './components/ChatArea';
import { LeadContextPanel } from './components/LeadContextPanel';
import { EnrichedConversation, Message, ChannelType, ConversationStatus } from './types';
import { useToast } from '@/components/ui/toast';

export default function OmnichannelPage() {
  const [conversations, setConversations] = useState<EnrichedConversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrichment, setEnrichment] = useState<any>(null);
  const [notes, setNotes] = useState<any[]>([]);

  const selectedConversation = conversations.find(c => c.id === selectedId) || null;

  // 1. Fetch conversations (with real status/assignee from DB)
  const fetchConversations = useCallback(async () => {
    try {
      setLoading(true);
      const waData = await api.whatsapp.getConversations();
      
      const enriched: EnrichedConversation[] = waData.map(c => ({
        id: c.id,
        phone: c.phone,
        client_name: c.client_name || c.phone,
        last_message: c.last_message || "",
        last_message_date: c.last_message_date,
        channel: 'whatsapp' as ChannelType,
        status: (c as any).status || 'open',
        priority: (c as any).priority || 'medium',
        tags: (c as any).tags || [],
        assignedTo: (c as any).assigned_to,
        unreadCount: c.unread_count || 0,
      }));

      setConversations(enriched);
    } catch (error) {
      logger.error('Failed to fetch conversations');
    } finally {
      setLoading(false);
    }
  }, []);

  // 2. Fetch messages & enrichment when selection changes
  useEffect(() => {
    if (!selectedId || !selectedConversation) return;

    const loadDetails = async () => {
      try {
        // Fetch Messages
        let msgs: any[] = [];
        if (selectedConversation.channel === 'whatsapp') {
          msgs = await api.whatsapp.getMessages(selectedConversation.phone);
        }
        
        // Fetch CRM Enrichment
        const enrichData = await api.workflow.getEnrichment(selectedId);
        setEnrichment(enrichData);

        // Fetch Internal Notes
        const notesData = await api.workflow.getNotes(selectedId);
        setNotes(notesData);
        
        // Combine real messages with internal notes for the UI
        const uiMessages: Message[] = [
          ...msgs.map((m: any) => ({
            id: m.id || Math.random().toString(),
            text: m.message_text || m.content || "",
            sender: m.direction === 'outbound' ? 'agent' : 'user',
            timestamp: m.timestamp || new Date().toISOString(),
            isInternalNote: false 
          })),
          ...notesData.map((n: any) => ({
            id: `note_${n.id}`,
            text: n.content,
            sender: 'agent',
            timestamp: n.created_at,
            isInternalNote: true
          }))
        ];

        setMessages(uiMessages.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()));
      } catch (error) {
        logger.error('Failed to load conversation details');
      }
    };

    loadDetails();
  }, [selectedId, selectedConversation]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // 3. Actions
  const handleSendMessage = async (text: string, isNote: boolean) => {
    if (!selectedConversation || !selectedId) return;

    if (isNote) {
      try {
        await api.workflow.addNote(selectedId, text, "current_user", "Team Member");
        // Reload notes
        const updatedNotes = await api.workflow.getNotes(selectedId);
        setNotes(updatedNotes);
        // Optimistic add to UI
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          text,
          sender: 'agent',
          timestamp: new Date().toISOString(),
          isInternalNote: true
        }]);
      } catch (e) { logger.error("Failed to add note"); }
    } else {
      try {
        if (selectedConversation.channel === 'whatsapp') {
          await api.whatsapp.sendMessage(selectedConversation.phone, text);
          // Add to UI
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            text,
            sender: 'agent',
            timestamp: new Date().toISOString(),
            isInternalNote: false
          }]);
        }
      } catch (error) { logger.error('Failed to send message'); }
    }
  };

  const handleAssign = async (userId: string) => {
    if (!selectedId) return;
    await api.workflow.assign(selectedId, userId);
    fetchConversations(); // Refresh list
  };

  const handleStatusChange = async (status: string) => {
    if (!selectedId) return;
    await api.workflow.updateStatus(selectedId, status);
    fetchConversations(); // Refresh list
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
          onStatusChange={handleStatusChange}
        />
      </div>

      {/* Pane 3: Intelligence Panel */}
      <LeadContextPanel 
        conversation={selectedConversation} 
        enrichment={enrichment}
        onAssign={handleAssign}
      />
    </div>
  );
}

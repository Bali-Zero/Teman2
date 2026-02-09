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
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const { toast, success, error: toastError } = useToast();

  const selectedConversation = conversations.find(c => c.id === selectedId) || null;

  // Fetch conversations (Inbox)
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
    } catch (err) {
      logger.error('Failed to fetch conversations');
      toastError('Sync Error', 'Could not fetch inbox from cloud.');
    } finally {
      setLoading(false);
    }
  }, [toastError]);

  // Load conversation details (Messages, CRM, Notes)
  useEffect(() => {
    if (!selectedId || !selectedConversation) return;

    const loadDetails = async () => {
      try {
        setIsDetailsLoading(true);
        
        // Parallel requests for better performance
        const [msgs, enrichData, notesData] = await Promise.all([
          selectedConversation.channel === 'whatsapp' ? api.whatsapp.getMessages(selectedConversation.phone) : Promise.resolve([]),
          api.workflow.getEnrichment(selectedId),
          api.workflow.getNotes(selectedId)
        ]);

        setEnrichment(enrichData);
        
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
      } catch (err) {
        logger.error('Failed to load conversation details');
      } finally {
        setIsDetailsLoading(false);
      }
    };

    loadDetails();
  }, [selectedId, selectedConversation]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleSendMessage = async (text: string, isNote: boolean) => {
    if (!selectedConversation || !selectedId) return;

    const optimisticId = Date.now().toString();
    const optimisticMsg: Message = {
      id: optimisticId,
      text,
      sender: 'agent',
      timestamp: new Date().toISOString(),
      isInternalNote: isNote
    };

    // Optimistic Update
    setMessages(prev => [...prev, optimisticMsg]);

    try {
      if (isNote) {
        await api.workflow.addNote(selectedId, text, "me", "Team");
        success('Note Saved', 'Internal note added to thread.');
      } else {
        if (selectedConversation.channel === 'whatsapp') {
          await api.whatsapp.sendMessage(selectedConversation.phone, text);
        }
      }
    } catch (err) {
      toastError('Send Failed', 'Message could not be delivered.');
      // Remove optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== optimisticId));
    }
  };

  const handleAssign = async (userId: string) => {
    if (!selectedId) return;
    try {
      await api.workflow.assign(selectedId, userId);
      success('Assigned', `Lead assigned to ${userId}`);
      fetchConversations();
    } catch (e) { toastError('Assignment Error', 'Could not assign lead.'); }
  };

  const handleStatusChange = async (status: string) => {
    if (!selectedId) return;
    try {
      await api.workflow.updateStatus(selectedId, status);
      success('Status Updated', `Conversation marked as ${status}`);
      fetchConversations();
    } catch (e) { toastError('Error', 'Could not update status.'); }
  };

  return (
    <div className="flex h-full w-full bg-background overflow-hidden selection:bg-red-100 selection:text-red-900">
      <InboxSidebar 
        conversations={conversations} 
        selectedId={selectedId} 
        onSelect={setSelectedId}
        isLoading={loading}
      />

      <div className="flex-1 flex flex-col min-w-0 shadow-inner">
        <ChatArea 
          conversation={selectedConversation} 
          messages={messages}
          onSendMessage={handleSendMessage}
          onStatusChange={handleStatusChange}
          isLoading={isDetailsLoading}
        />
      </div>

      <LeadContextPanel 
        conversation={selectedConversation} 
        enrichment={enrichment}
        onAssign={handleAssign}
        isLoading={isDetailsLoading}
      />
    </div>
  );
}
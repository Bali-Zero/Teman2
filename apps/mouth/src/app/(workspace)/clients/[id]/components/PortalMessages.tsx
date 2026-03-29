'use client';

import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, Send, CheckCheck, Clock, User, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { PortalMessageThread } from '@/lib/api/crm/crm.types';

export function PortalMessages({
  clientId,
  clientName,
}: {
  clientId: number;
  clientName: string;
}) {
  const [messages, setMessages] = useState<PortalMessageThread[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newMessage, setNewMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadMessages = async () => {
    try {
      const data = await api.crm.getPortalMessages(clientId);
      setMessages(data.messages || []);
      // Mark unread client messages as read
      for (const msg of data.messages || []) {
        if (msg.direction === 'client_to_team' && !msg.read_at) {
          api.crm.markPortalMessageRead(clientId, msg.id).catch(() => {});
        }
      }
    } catch {
      // Silently fail — portal messages are optional
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMessages();
    const interval = setInterval(loadMessages, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, [clientId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!newMessage.trim()) return;
    setIsSending(true);
    try {
      await api.crm.sendPortalMessage(clientId, newMessage.trim());
      setNewMessage('');
      await loadMessages();
      toast.success('Message sent to client portal');
    } catch (err) {
      toast.error('Failed to send', { description: (err as Error).message });
    } finally {
      setIsSending(false);
    }
  };

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  };

  const unreadCount = messages.filter(
    (m) => m.direction === 'client_to_team' && !m.read_at
  ).length;

  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col"
      style={{
        background: 'rgba(30, 30, 35, 0.7)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4" style={{ color: 'var(--bz-accent)' }} />
          <h3 className="font-semibold text-sm text-[var(--bz-text-1)]">Portal Messages</h3>
          {unreadCount > 0 && (
            <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
              {unreadCount}
            </span>
          )}
        </div>
        <span className="text-[11px] text-[var(--bz-text-2)]">
          {clientName} &middot; my.balizero.com
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 max-h-[300px] overflow-y-auto px-4 py-3 space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-5 h-5 border-2 border-[var(--bz-accent)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-8 text-[var(--bz-text-2)] text-sm">
            <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p>No portal messages yet</p>
            <p className="text-xs mt-1 opacity-60">
              Send a message visible on {clientName}&apos;s portal
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isTeam = msg.direction === 'team_to_client';
            return (
              <div
                key={msg.id}
                className={`flex gap-2 ${isTeam ? 'justify-end' : 'justify-start'}`}
              >
                {!isTeam && (
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0 mt-1">
                    <User className="w-3 h-3 text-blue-400" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    isTeam
                      ? 'bg-[var(--bz-accent)]/15 text-[var(--bz-text-1)]'
                      : 'bg-blue-500/10 text-[var(--bz-text-1)]'
                  }`}
                >
                  {msg.subject && (
                    <p className="text-xs font-semibold mb-1 opacity-70">{msg.subject}</p>
                  )}
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <div className="flex items-center gap-1 mt-1 text-[10px] text-[var(--bz-text-2)]">
                    <span>{formatTime(msg.created_at)}</span>
                    {isTeam && msg.sent_by && (
                      <span>&middot; {msg.sent_by.split('@')[0]}</span>
                    )}
                    {isTeam && (
                      <CheckCheck
                        className={`w-3 h-3 ml-1 ${msg.read_at ? 'text-blue-400' : 'text-[var(--bz-text-2)]'}`}
                      />
                    )}
                    {!isTeam && !msg.read_at && (
                      <span className="text-red-400 font-semibold ml-1">NEW</span>
                    )}
                  </div>
                </div>
                {isTeam && (
                  <div className="w-6 h-6 rounded-full bg-[var(--bz-accent)]/20 flex items-center justify-center shrink-0 mt-1">
                    <Bot className="w-3 h-3 text-[var(--bz-accent)]" />
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-t"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <input
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder={`Message ${clientName}...`}
          className="flex-1 bg-transparent border border-[rgba(255,255,255,0.1)] rounded-lg px-3 py-2 text-sm text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-2)] focus:outline-none focus:border-[var(--bz-accent)]/50"
        />
        <Button
          size="sm"
          onClick={handleSend}
          disabled={isSending || !newMessage.trim()}
          className="gap-1"
        >
          <Send className="w-3.5 h-3.5" />
          {isSending ? 'Sending...' : 'Send'}
        </Button>
      </div>
    </div>
  );
}

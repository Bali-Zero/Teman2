'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Loader2, Send, MessageCircle, User, Users } from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { logger } from '@/lib/logger';
import type { PortalMessage, MessagesResponse } from '@/lib/api/portal/portal.types';
import { Button } from '@/components/ui/button';

const POLL_INTERVAL = 30000; // 30 seconds

const PAGE_SIZE = 100;

export default function ChatPage() {
  const { error, success } = useToast();
  const [messages, setMessages] = useState<PortalMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [isSending, setIsSending] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load messages
  const loadMessages = useCallback(
    async (silent = false) => {
      try {
        if (!silent) setIsLoading(true);
        const data: MessagesResponse = await api.portal.getMessages(PAGE_SIZE, 0);
        const sortedMessages = [...data.messages].sort(
          (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        );
        setMessages(sortedMessages);
        setUnreadCount(data.unreadCount);
        setOffset(PAGE_SIZE);
        setHasMore(data.messages.length === PAGE_SIZE);
      } catch (err) {
        if (!silent) {
          error('Failed to load messages', 'Please try again later');
        }
        logger.error('Failed to load portal messages', {}, err as Error);
      } finally {
        setIsLoading(false);
      }
    },
    [error]
  );

  // Load earlier messages (prepend)
  const loadMoreMessages = useCallback(async () => {
    try {
      setIsLoadingMore(true);
      const data: MessagesResponse = await api.portal.getMessages(PAGE_SIZE, offset);
      if (data.messages.length === 0) {
        setHasMore(false);
        return;
      }
      const older = [...data.messages].sort(
        (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
      );
      setMessages((prev) => [...older, ...prev]);
      setOffset((prev) => prev + PAGE_SIZE);
      setHasMore(data.messages.length === PAGE_SIZE);
    } catch (err) {
      logger.error('Failed to load earlier messages', {}, err as Error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [offset]);

  // Mark visible messages as read
  const markVisibleMessagesAsRead = useCallback(async () => {
    const unreadMessages = messages.filter(
      (msg) => msg.direction === 'team_to_client' && !msg.readAt
    );

    for (const msg of unreadMessages) {
      try {
        await api.portal.markMessageRead(parseInt(msg.id));
      } catch (err) {
        logger.error('Failed to mark message as read', {}, err as Error);
      }
    }

    // Refresh to update read status
    if (unreadMessages.length > 0) {
      loadMessages(true);
    }
  }, [messages, loadMessages]);

  // Initial load
  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  // Polling for new messages
  useEffect(() => {
    const interval = setInterval(() => {
      loadMessages(true);
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [loadMessages]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Mark messages as read when they become visible
  useEffect(() => {
    if (!isLoading && messages.length > 0) {
      const timer = setTimeout(() => {
        markVisibleMessagesAsRead();
      }, 1000); // Wait 1s before marking as read

      return () => clearTimeout(timer);
    }
  }, [messages, isLoading, markVisibleMessagesAsRead]);

  // Send message
  const handleSendMessage = async () => {
    const trimmedMessage = newMessage.trim();
    if (!trimmedMessage || isSending) return;

    try {
      setIsSending(true);
      const sentMessage = await api.portal.sendMessage({
        content: trimmedMessage,
      });
      setMessages((prev) => [...prev, sentMessage]);
      setNewMessage('');
      inputRef.current?.focus();
    } catch (err) {
      error('Failed to send message', 'Please try again');
      logger.error('Failed to send portal message', {}, err as Error);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    } else if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday';
    } else {
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined,
      });
    }
  };

  // Group messages by date
  const groupedMessages = messages.reduce(
    (groups, message) => {
      const date = new Date(message.createdAt).toDateString();
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(message);
      return groups;
    },
    {} as Record<string, PortalMessage[]>
  );

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--bz-accent-warm)' }} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] md:h-[calc(100vh-140px)] animate-in fade-in duration-500">
      {/* Header */}
      <section
        className="flex-shrink-0 pb-4 border-b sticky top-0 z-10"
        style={{ borderColor: 'var(--bz-border)', background: 'var(--bz-bg)' }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Messages</h1>
            <p style={{ color: 'var(--bz-text-2)' }}>Chat with your Bali Zero team</p>
          </div>
          <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--bz-text-2)' }}>
            <Users className="w-4 h-4" />
            <span>Bali Zero Team</span>
          </div>
        </div>
        {unreadCount > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <div
              className="px-3 py-1.5 text-sm rounded-full inline-flex items-center gap-1.5"
              style={{
                background: 'rgba(201,169,110,0.12)',
                color: 'var(--bz-accent-warm)',
              }}
            >
              <MessageCircle className="w-4 h-4" />
              {unreadCount} unread message{unreadCount !== 1 ? 's' : ''}
            </div>
            <button
              onClick={markVisibleMessagesAsRead}
              className="text-xs underline underline-offset-2 opacity-60 hover:opacity-100 transition-opacity"
              style={{ color: 'var(--bz-text-2)' }}
            >
              Mark all as read
            </button>
          </div>
        )}
      </section>

      {/* Messages Container */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto py-4 space-y-4 scrollbar-thin scrollbar-thumb-neutral-600"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <MessageCircle className="w-16 h-16 mb-4" style={{ color: 'var(--bz-text-3)' }} />
            <h3 className="text-lg font-semibold" style={{ color: 'var(--bz-text-2)' }}>
              No messages yet
            </h3>
            <p className="text-sm mt-1 max-w-xs" style={{ color: 'var(--bz-text-3)' }}>
              Start a conversation with your Bali Zero team. We're here to help!
            </p>
          </div>
        ) : (
          <>
            {hasMore && (
              <div className="text-center py-2">
                <button
                  onClick={loadMoreMessages}
                  disabled={isLoadingMore}
                  className="text-xs px-3 py-1.5 rounded-full border transition-opacity hover:opacity-80 disabled:opacity-40"
                  style={{
                    borderColor: 'var(--bz-border)',
                    color: 'var(--bz-text-2)',
                    background: 'rgba(255,255,255,0.03)',
                  }}
                >
                  {isLoadingMore ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                  Load earlier messages
                </button>
              </div>
            )}
            {Object.entries(groupedMessages).map(([date, dateMessages]) => (
              <div key={date}>
                {/* Date Separator */}
                <div className="flex items-center gap-3 my-4">
                  <div className="flex-1 h-px" style={{ background: 'var(--bz-border)' }} />
                  <span className="text-xs font-medium px-2" style={{ color: 'var(--bz-text-2)' }}>
                    {formatDate(dateMessages[0].createdAt)}
                  </span>
                  <div className="flex-1 h-px" style={{ background: 'var(--bz-border)' }} />
                </div>

                {/* Messages for this date */}
                <div className="space-y-3">
                  {dateMessages.map((message) => (
                    <MessageBubble key={message.id} message={message} formatTime={formatTime} />
                  ))}
                </div>
              </div>
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 pt-4 border-t" style={{ borderColor: 'var(--bz-border)' }}>
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            aria-label="Type a message to Bali Zero team"
            id="message-input"
            disabled={isSending}
            className={cn(
              'flex-1 px-4 py-3 rounded-xl border',
              'focus:outline-none focus:ring-2',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderColor: 'rgba(255,255,255,0.05)',
              color: 'var(--bz-text-1)',
            }}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!newMessage.trim() || isSending}
            size="icon"
            className="h-12 w-12 rounded-xl"
          >
            {isSending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </Button>
        </div>
        <p className="text-xs mt-2 text-center" style={{ color: 'var(--bz-text-3)' }}>
          Messages are typically responded to within 24 hours
        </p>
      </div>
    </div>
  );
}

// Message Bubble Component
function MessageBubble({
  message,
  formatTime,
}: {
  message: PortalMessage;
  formatTime: (date: string) => string;
}) {
  const isFromTeam = message.direction === 'team_to_client';
  const isUnread = isFromTeam && !message.readAt;

  return (
    <div className={cn('flex gap-2', isFromTeam ? 'justify-start' : 'justify-end')}>
      {/* Team Avatar */}
      {isFromTeam && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(201,169,110,0.12)' }}
        >
          <Users className="w-4 h-4" style={{ color: 'var(--bz-accent-warm)' }} />
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          'max-w-[80%] md:max-w-[70%] rounded-2xl px-4 py-2.5',
          isFromTeam ? 'rounded-tl-sm' : 'rounded-tr-sm',
          isUnread && 'ring-2'
        )}
        style={
          isFromTeam
            ? {
                background: 'rgba(255,255,255,0.03)',
                backdropFilter: 'blur(12px)',
                boxShadow: isUnread ? '0 0 0 2px rgba(201,169,110,0.3)' : undefined,
              }
            : { background: 'var(--bz-accent-warm)', color: '#0c0c0e' }
        }
      >
        {/* Sender name for team messages */}
        {isFromTeam && message.sentBy && (
          <p className="text-xs font-medium mb-1" style={{ color: 'var(--bz-accent-warm)' }}>
            {message.sentBy}
          </p>
        )}

        {/* Subject if present */}
        {message.subject && (
          <p
            className="text-sm font-semibold mb-1"
            style={{ color: isFromTeam ? 'var(--bz-text-1)' : '#0c0c0e' }}
          >
            {message.subject}
          </p>
        )}

        {/* Message content */}
        <p
          className="text-sm whitespace-pre-wrap break-words"
          style={{ color: isFromTeam ? 'var(--bz-text-1)' : '#0c0c0e' }}
        >
          {message.content}
        </p>

        {/* Time */}
        <p
          className="text-[10px] mt-1"
          style={{
            color: isFromTeam ? 'var(--bz-text-2)' : 'rgba(12,12,14,0.6)',
          }}
        >
          {formatTime(message.createdAt)}
          {!isFromTeam && message.readAt && ' • Read'}
        </p>
      </div>

      {/* User Avatar */}
      {!isFromTeam && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{ background: 'var(--bz-accent-warm)' }}
        >
          <User className="w-4 h-4" style={{ color: '#0c0c0e' }} />
        </div>
      )}
    </div>
  );
}

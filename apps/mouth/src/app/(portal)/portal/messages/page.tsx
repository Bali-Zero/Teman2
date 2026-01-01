'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageSquare,
  Send,
  User,
  Users,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { PortalMessage } from '@/lib/api/portal/portal.types';

export default function MessagesPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<PortalMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadMessages = useCallback(async () => {
    try {
      const data = await api.portal.getMessages(50, 0);
      setMessages(data.messages);
      setError(null);
    } catch (err) {
      console.error('Failed to load messages:', err);
      if (!messages.length) {
        setError('Unable to load messages. Please try again.');
      }
    }
  }, [messages.length]);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await loadMessages();
      setIsLoading(false);
    };

    init();

    pollIntervalRef.current = setInterval(loadMessages, 30000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!newMessage.trim() || isSending) return;

    setIsSending(true);

    const tempId = `temp-${Date.now()}`;
    const tempMessage: PortalMessage = {
      id: tempId,
      content: newMessage,
      direction: 'client_to_team',
      sentBy: 'You',
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempMessage]);
    const messageToSend = newMessage;
    setNewMessage('');

    try {
      const sentMessage = await api.portal.sendMessage({ content: messageToSend });
      setMessages((prev) => prev.map(m => m.id === tempId ? sentMessage : m));
    } catch (err) {
      console.error('Failed to send message:', err);
      setMessages((prev) => prev.filter(m => m.id !== tempId));
      setNewMessage(messageToSend);
    } finally {
      setIsSending(false);
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
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
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const groupedMessages = messages.reduce((acc, message) => {
    const dateKey = new Date(message.createdAt).toDateString();
    if (!acc[dateKey]) {
      acc[dateKey] = [];
    }
    acc[dateKey].push(message);
    return acc;
  }, {} as Record<string, PortalMessage[]>);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-[#1A1D24] rounded w-64"></div>
        <div className="h-96 bg-[#1A1D24] rounded-xl"></div>
      </div>
    );
  }

  if (error && !messages.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">Unable to load messages</h2>
        <p className="text-[#9AA0AE] mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#4FD1C5] text-[#0B0E13] font-medium rounded-lg hover:bg-[#38B2AC] transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-semibold text-[#E6E7EB]">Messages</h1>
        <p className="text-[#9AA0AE] mt-1">Communicate with our team</p>
      </div>

      {/* Messages Container */}
      <div className="flex-1 bg-[#1A1D24] rounded-xl border border-white/5 flex flex-col overflow-hidden">
        {/* Message List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {Object.keys(groupedMessages).length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full py-12">
              <MessageSquare className="w-12 h-12 text-[#9AA0AE] mb-4" />
              <h3 className="font-medium text-[#E6E7EB]">No messages yet</h3>
              <p className="text-sm text-[#9AA0AE] mt-1">Start a conversation with our team</p>
            </div>
          ) : (
            Object.entries(groupedMessages).map(([dateKey, dateMessages]) => (
              <div key={dateKey}>
                {/* Date Separator */}
                <div className="flex items-center justify-center mb-4">
                  <span className="px-3 py-1 bg-[#2a2a2a] rounded-full text-xs text-[#9AA0AE]">
                    {formatDate(dateMessages[0].createdAt)}
                  </span>
                </div>

                {/* Messages */}
                <div className="space-y-4">
                  {dateMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.direction === 'client_to_team' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] ${
                          message.direction === 'client_to_team'
                            ? 'bg-[#4FD1C5] text-[#0B0E13] rounded-2xl rounded-tr-md'
                            : 'bg-[#2a2a2a] text-[#E6E7EB] rounded-2xl rounded-tl-md'
                        } p-4`}
                      >
                        {/* Sender */}
                        <div className={`flex items-center gap-2 mb-2 ${message.direction === 'client_to_team' ? 'justify-end' : ''}`}>
                          <div className={`p-1 rounded-full ${message.direction === 'client_to_team' ? 'bg-[#38B2AC]' : 'bg-[#1A1D24]'}`}>
                            {message.direction === 'client_to_team' ? (
                              <User className={`w-3 h-3 ${message.direction === 'client_to_team' ? 'text-[#0B0E13]' : 'text-[#9AA0AE]'}`} />
                            ) : (
                              <Users className="w-3 h-3 text-[#9AA0AE]" />
                            )}
                          </div>
                          <span className={`text-xs ${message.direction === 'client_to_team' ? 'text-[#0B0E13]/70' : 'text-[#9AA0AE]'}`}>
                            {message.sentBy}
                          </span>
                        </div>

                        {/* Content */}
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                        {/* Time */}
                        <div className={`flex items-center gap-1 mt-2 ${message.direction === 'client_to_team' ? 'justify-end' : ''}`}>
                          <Clock className={`w-3 h-3 ${message.direction === 'client_to_team' ? 'text-[#0B0E13]/50' : 'text-[#9AA0AE]'}`} />
                          <span className={`text-xs ${message.direction === 'client_to_team' ? 'text-[#0B0E13]/50' : 'text-[#9AA0AE]'}`}>
                            {formatTime(message.createdAt)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Message Input */}
        <div className="p-4 border-t border-white/5">
          <div className="flex items-end gap-3">
            <textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Type your message..."
              className="flex-1 px-4 py-3 bg-[#2a2a2a] border border-white/10 rounded-xl text-[#E6E7EB] placeholder-[#9AA0AE] resize-none focus:outline-none focus:ring-2 focus:ring-[#4FD1C5] focus:border-transparent"
              rows={1}
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
            <button
              onClick={handleSendMessage}
              disabled={!newMessage.trim() || isSending}
              className={`p-3 rounded-xl transition-colors ${
                newMessage.trim() && !isSending
                  ? 'bg-[#4FD1C5] text-[#0B0E13] hover:bg-[#38B2AC]'
                  : 'bg-[#1A1D24] text-[#9AA0AE] cursor-not-allowed'
              }`}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <p className="text-xs text-[#9AA0AE] mt-2">Press Enter to send, Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  );
}

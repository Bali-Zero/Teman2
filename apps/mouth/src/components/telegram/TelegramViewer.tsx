"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Send,
  User,
  ArrowLeft,
  MoreHorizontal,
  Check,
  CheckCheck,
  MessageCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TelegramMessage } from "@/lib/api/telegram/telegram.types";
import type { Client } from "@/lib/api/crm/crm.types";
import { logger } from "@/lib/logger";

interface TelegramViewerProps {
  chatId: string | number | null;
  messages: TelegramMessage[];
  client?: Client | null;
  onClose: () => void;
  onSendMessage: (text: string, replyToMessageId?: string) => Promise<void>;
  isLoading?: boolean;
}

export function TelegramViewer({
  chatId,
  messages,
  client,
  onClose,
  onSendMessage,
  isLoading,
}: TelegramViewerProps) {
  const [messageText, setMessageText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!messageText.trim() || !chatId || isSending) return;

    setIsSending(true);
    try {
      await onSendMessage(messageText.trim());
      setMessageText("");
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }
    } catch (error) {
      logger.error("Failed to send message:", {}, error as Error);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    const isYesterday =
      date.toDateString() === new Date(now.getTime() - 86400000).toDateString();

    if (isToday) return "Today";
    if (isYesterday) return "Yesterday";
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  // Group messages by date
  const groupedMessages = messages.reduce(
    (groups, message) => {
      const date = formatDate(message.timestamp);
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(message);
      return groups;
    },
    {} as Record<string, TelegramMessage[]>,
  );

  if (!chatId) {
    return (
      <div className="flex-1 flex flex-col h-full bg-[var(--background)] items-center justify-center">
        <div className="text-center p-8">
          <MessageCircle className="w-16 h-16 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
          <p className="text-sm text-[var(--foreground-muted)]">
            Select a conversation to view messages
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--background)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[var(--background-elevated)] transition-colors lg:hidden"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
            {client ? (
              <User className="w-6 h-6 text-blue-500" />
            ) : (
              <Send className="w-6 h-6 text-blue-500" />
            )}
          </div>
          <div>
            <h2 className="text-sm font-semibold text-[var(--foreground)]">
              {client?.full_name || `Chat ${String(chatId).slice(-4)}`}
            </h2>
            {client?.email && (
              <p className="text-xs text-[var(--foreground-muted)]">
                {client.email}
              </p>
            )}
          </div>
        </div>
        <button className="p-2 rounded-lg hover:bg-[var(--background-elevated)] transition-colors">
          <MoreHorizontal className="w-5 h-5" />
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoading && messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-sm text-[var(--foreground-muted)]">
                Loading messages...
              </p>
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <MessageCircle className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">
                No messages yet
              </p>
            </div>
          </div>
        ) : (
          Object.entries(groupedMessages).map(([date, dateMessages]) => (
            <div key={date}>
              {/* Date Separator */}
              <div className="flex items-center justify-center my-4">
                <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)] text-xs text-[var(--foreground-muted)]">
                  {date}
                </span>
              </div>

              {/* Messages for this date */}
              {dateMessages.map((message) => {
                const isOutbound = message.direction === "outbound";

                return (
                  <div
                    key={message.id}
                    className={cn(
                      "flex mb-2",
                      isOutbound ? "justify-end" : "justify-start",
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-[70%] rounded-lg px-4 py-2",
                        isOutbound
                          ? "bg-blue-500 text-white"
                          : "bg-[var(--background-elevated)] text-[var(--foreground)]",
                      )}
                    >
                      <p className="text-sm whitespace-pre-wrap break-words">
                        {message.message_text}
                      </p>
                      <div className="flex items-center justify-end gap-1 mt-1">
                        <span
                          className={cn(
                            "text-xs",
                            isOutbound
                              ? "text-blue-100"
                              : "text-[var(--foreground-muted)]",
                          )}
                        >
                          {formatTime(message.timestamp)}
                        </span>
                        {isOutbound && (
                          <span className="ml-1">
                            {message.status === "read" ? (
                              <CheckCheck className="w-3 h-3 text-blue-100" />
                            ) : message.status === "delivered" ? (
                              <CheckCheck className="w-3 h-3 text-blue-100 opacity-50" />
                            ) : (
                              <Check className="w-3 h-3 text-blue-100 opacity-50" />
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-[var(--border)] bg-[var(--background-secondary)] p-4">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={messageText}
            onChange={(e) => {
              setMessageText(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
            }}
            onKeyPress={handleKeyPress}
            placeholder="Type a message..."
            rows={1}
            className={cn(
              "flex-1 px-4 py-2 rounded-lg border border-[var(--border)]",
              "bg-[var(--background)] text-[var(--foreground)]",
              "placeholder:text-[var(--foreground-muted)]",
              "focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50",
              "resize-none max-h-[120px]",
            )}
            disabled={isSending || !chatId}
          />
          <button
            onClick={handleSend}
            disabled={!messageText.trim() || isSending || !chatId}
            className={cn(
              "p-3 rounded-lg transition-colors flex-shrink-0",
              messageText.trim() && !isSending && chatId
                ? "bg-blue-500 text-white hover:bg-blue-600"
                : "bg-[var(--background-elevated)] text-[var(--foreground-muted)] cursor-not-allowed",
            )}
          >
            {isSending ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

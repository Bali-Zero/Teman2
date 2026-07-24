"use client";

/**
 * Portal Chat — client ↔ Bali Zero team messaging.
 *
 * WS3 slice 6 (GARUDA Day Edition, 2026-07-26): day-theme token alignment,
 * mirroring slices 1-4 (portal home / matters / billing / process).
 * - Masthead: copper rule + Cormorant serif (--font-serif) in --tx-pure.
 * - Team bubble: --bz-card warm-paper card + hairline --bz-border (+ concept
 *   .panel shadow); own bubble: --bz-accent-warm fill + --bz-on-warm fg
 *   (theme-aware — ink on sand dark 8.43:1, white on daylight-gold light
 *   4.86:1, both AA). Sender/team distinction is readable without color:
 *   alignment (left/right), avatar, sender label, "• Read" marker.
 * - Copper small text reads --bz-copper-text (5.04:1 on paper). The 12%-tint
 *   chip pattern is NOT used under small copper text (tint drops it to
 *   ~4.4:1 on BOTH themes) — chips/tabs get a hairline copper border on the
 *   page surface instead.
 * - No zantara/AI accent here: this is team messaging, not the AI assistant.
 */

import React, { useEffect, useState, useRef, useCallback } from "react";
import { Loader2, Send, MessageCircle, User, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type {
  PortalMessage,
  MessagesResponse,
} from "@/lib/api/portal/portal.types";
import { Button } from "@/components/ui/button";

const POLL_INTERVAL = 30000; // 30 seconds

const PAGE_SIZE = 100;

export default function ChatPage() {
  const { error } = useToast();
  const [messages, setMessages] = useState<PortalMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [isSending, setIsSending] = useState(false);
  const [newMessage, setNewMessage] = useState("");
  const [activeThread, setActiveThread] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // Ref mirror of messages — lets markVisibleMessagesAsRead read current
  // messages without taking `messages` as a useCallback dep (which would
  // recreate the callback on every fetch and re-trigger the mark-as-read
  // effect, causing the infinite-fetch loop).
  const messagesRef = useRef<PortalMessage[]>([]);
  // useToast returns inline arrow functions — new identity on every render.
  // Mirror in a ref so loadMessages can have empty deps and stay stable.
  const errorRef = useRef(error);
  useEffect(() => {
    errorRef.current = error;
  });

  // Load messages
  const loadMessages = useCallback(
    async (silent = false) => {
      try {
        if (!silent) setIsLoading(true);
        const data: MessagesResponse = await api.portal.getMessages(
          PAGE_SIZE,
          0,
        );
        const sortedMessages = [...data.messages].sort(
          (a, b) =>
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
        );
        messagesRef.current = sortedMessages;
        setMessages(sortedMessages);
        setUnreadCount(data.unreadCount);
        setOffset(PAGE_SIZE);
        setHasMore(data.messages.length === PAGE_SIZE);
      } catch (err) {
        if (!silent) {
          errorRef.current("Failed to load messages", "Please try again later");
        }
        logger.error("Failed to load portal messages", {}, err as Error);
      } finally {
        setIsLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // Load earlier messages (prepend)
  const loadMoreMessages = useCallback(async () => {
    try {
      setIsLoadingMore(true);
      const data: MessagesResponse = await api.portal.getMessages(
        PAGE_SIZE,
        offset,
      );
      if (data.messages.length === 0) {
        setHasMore(false);
        return;
      }
      const older = [...data.messages].sort(
        (a, b) =>
          new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
      );
      setMessages((prev) => {
        const next = [...older, ...prev];
        messagesRef.current = next;
        return next;
      });
      setOffset((prev) => prev + PAGE_SIZE);
      setHasMore(data.messages.length === PAGE_SIZE);
    } catch (err) {
      errorRef.current("Failed to load earlier messages", "Please try again");
      logger.error("Failed to load earlier messages", {}, err as Error);
    } finally {
      setIsLoadingMore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  // Mark visible messages as read.
  // Reads from messagesRef (not from the `messages` state variable) so this
  // callback is stable and does NOT need `messages` in its dep array.
  // That breaks the cycle: messages → markVisibleMessagesAsRead → effect →
  // loadMessages → setMessages → messages → … (was causing ~1167 fetches).
  const markVisibleMessagesAsRead = useCallback(async () => {
    const unreadMessages = messagesRef.current.filter(
      (msg) => msg.direction === "team_to_client" && !msg.readAt,
    );

    for (const msg of unreadMessages) {
      try {
        await api.portal.markMessageRead(parseInt(msg.id));
      } catch (err) {
        logger.error("Failed to mark message as read", {}, err as Error);
      }
    }

    // Refresh to update read status
    if (unreadMessages.length > 0) {
      loadMessages(true);
    }
  }, [loadMessages]);

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
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Mark messages as read once after the initial load completes.
  // Deps: only [isLoading, markVisibleMessagesAsRead] — NOT `messages`.
  // Removing `messages` from deps is intentional: we read from messagesRef
  // inside the callback so we always see the latest list without causing
  // this effect to re-fire on every fetch (which was the infinite-loop root).
  const prevIsLoadingRef = useRef(true);
  useEffect(() => {
    // Fire when isLoading transitions from true → false (initial load done)
    if (
      prevIsLoadingRef.current &&
      !isLoading &&
      messagesRef.current.length > 0
    ) {
      const timer = setTimeout(() => {
        markVisibleMessagesAsRead();
      }, 1000);
      prevIsLoadingRef.current = false;
      return () => clearTimeout(timer);
    }
    prevIsLoadingRef.current = isLoading;
  }, [isLoading, markVisibleMessagesAsRead]);

  // Send message
  const handleSendMessage = async () => {
    const trimmedMessage = newMessage.trim();
    if (!trimmedMessage || isSending) return;

    try {
      setIsSending(true);
      const sentMessage = await api.portal.sendMessage({
        content: trimmedMessage,
        practiceId: activeThread ?? undefined,
      });
      setMessages((prev) => [...prev, sentMessage]);
      setNewMessage("");
      inputRef.current?.focus();
    } catch (err) {
      error("Failed to send message", "Please try again");
      logger.error("Failed to send portal message", {}, err as Error);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return "Today";
    } else if (date.toDateString() === yesterday.toDateString()) {
      return "Yesterday";
    } else {
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year:
          date.getFullYear() !== today.getFullYear() ? "numeric" : undefined,
      });
    }
  };

  // Compute unique threads from messages
  const threads = React.useMemo(() => {
    const threadMap = new Map<
      number | null,
      { id: number | null; name: string; unread: number }
    >();
    threadMap.set(null, { id: null, name: "All", unread: 0 });

    for (const msg of messages) {
      const pid = msg.practiceId ?? null;
      if (pid !== null && !threadMap.has(pid)) {
        threadMap.set(pid, {
          id: pid,
          name: msg.practiceName || `Practice #${pid}`,
          unread: 0,
        });
      }
      if (msg.direction === "team_to_client" && !msg.readAt) {
        const t = threadMap.get(pid);
        if (t) t.unread++;
        const allT = threadMap.get(null);
        if (allT) allT.unread++;
      }
    }
    return Array.from(threadMap.values());
  }, [messages]);

  // Filter messages by active thread
  const filteredMessages = React.useMemo(() => {
    if (activeThread === null) return messages;
    return messages.filter((m) => (m.practiceId ?? null) === activeThread);
  }, [messages, activeThread]);

  // Group messages by date
  const groupedMessages = filteredMessages.reduce(
    (groups, message) => {
      const date = new Date(message.createdAt).toDateString();
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(message);
      return groups;
    },
    {} as Record<string, PortalMessage[]>,
  );

  if (isLoading) {
    return (
      <div className="flex flex-col h-[calc(100vh-180px)] md:h-[calc(100vh-140px)] animate-in fade-in duration-500">
        <div
          className="flex-shrink-0 pb-4 border-b"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <div
            className="h-6 w-32 rounded animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-4 w-48 rounded mt-1 animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
        </div>
        <div className="flex-1 py-4 space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className={`flex gap-3 ${i % 2 === 0 ? "flex-row-reverse" : ""}`}
            >
              <div
                className="w-8 h-8 rounded-full flex-shrink-0 animate-pulse"
                style={{ background: "var(--bz-border)" }}
              />
              <div
                className={`h-16 rounded-xl animate-pulse ${i % 2 === 0 ? "w-2/3" : "w-3/4"}`}
                style={{ background: "var(--bz-border)", opacity: 0.5 }}
              />
            </div>
          ))}
        </div>
        <div
          className="flex-shrink-0 pt-3 border-t"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <div
            className="h-12 w-full rounded-xl animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.4 }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] md:h-[calc(100vh-140px)] animate-in fade-in duration-500">
      {/* Header */}
      <section
        className="flex-shrink-0 pb-4 border-b sticky top-0 z-10"
        style={{ borderColor: "var(--bz-border)", background: "var(--bz-bg)" }}
      >
        <div className="flex items-center justify-between">
          <div>
            {/* Day masthead: copper rule + Cormorant serif in --tx-pure */}
            <div
              aria-hidden="true"
              className="w-14 h-[3px] rounded-sm mb-3 bg-[var(--bz-copper)]"
            />
            <h1
              className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              Messages
            </h1>
            <p
              className="text-sm mt-1"
              style={{ color: "var(--tx-secondary)" }}
            >
              Chat with your Bali Zero team
            </p>
          </div>
          <div
            className="flex items-center gap-2 text-sm"
            style={{ color: "var(--bz-text-2)" }}
          >
            <Users className="w-4 h-4" />
            <span>Bali Zero Team</span>
          </div>
        </div>
        {unreadCount > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <div
              className="px-3 py-1.5 text-sm rounded-full inline-flex items-center gap-1.5 border"
              style={{
                // Hairline copper border, NOT a 12% tint fill: small copper
                // text on a copper tint measures ~4.4:1 on both themes
                // (below the 4.5:1 AA floor); on the page surface
                // --bz-copper-text is 5.04:1 (paper) / 5.15:1 (anthracite).
                borderColor:
                  "color-mix(in srgb, var(--bz-copper) 40%, transparent)",
                color: "var(--bz-copper-text)",
              }}
            >
              <MessageCircle className="w-4 h-4" />
              {unreadCount} unread message{unreadCount !== 1 ? "s" : ""}
            </div>
            <button
              onClick={markVisibleMessagesAsRead}
              className="text-xs underline underline-offset-2 opacity-60 hover:opacity-100 transition-opacity"
              style={{ color: "var(--bz-text-2)" }}
            >
              Mark all as read
            </button>
          </div>
        )}
      </section>

      {/* Thread Tabs */}
      {threads.length > 1 && (
        <div
          className="flex-shrink-0 flex gap-1 py-2 overflow-x-auto scrollbar-hide border-b"
          style={{ borderColor: "var(--bz-border)" }}
        >
          {threads.map((thread) => (
            <button
              key={thread.id ?? "all"}
              onClick={() => setActiveThread(thread.id)}
              className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 border"
              style={
                activeThread === thread.id
                  ? {
                      borderColor:
                        "color-mix(in srgb, var(--bz-copper) 40%, transparent)",
                      color: "var(--bz-copper-text)",
                    }
                  : {
                      borderColor: "transparent",
                      color: "var(--bz-text-2)",
                    }
              }
            >
              {thread.name}
              {thread.unread > 0 && (
                <span
                  className="px-1.5 py-0.5 rounded-full text-[10px] font-bold"
                  style={{
                    background: "var(--bz-accent-warm)",
                    color: "var(--bz-on-warm)",
                  }}
                >
                  {thread.unread}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Messages Container */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto py-4 space-y-4 scrollbar-thin scrollbar-thumb-[var(--bz-border-hover)]"
      >
        {filteredMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <MessageCircle
              className="w-16 h-16 mb-4"
              style={{ color: "var(--bz-text-3)" }}
            />
            <h3
              className="text-lg font-semibold"
              style={{ color: "var(--bz-text-2)" }}
            >
              No messages yet
            </h3>
            <p
              className="text-sm mt-1 max-w-xs"
              style={{ color: "var(--bz-text-3)" }}
            >
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
                    borderColor: "var(--bz-border)",
                    color: "var(--bz-text-2)",
                    background: "var(--bz-card)",
                  }}
                >
                  {isLoadingMore ? (
                    <Loader2 className="w-3 h-3 animate-spin inline mr-1" />
                  ) : null}
                  Load earlier messages
                </button>
              </div>
            )}
            {Object.entries(groupedMessages).map(([date, dateMessages]) => (
              <div key={date}>
                {/* Date Separator */}
                <div className="flex items-center gap-3 my-4">
                  <div
                    className="flex-1 h-px"
                    style={{ background: "var(--bz-border)" }}
                  />
                  <span
                    className="text-xs font-medium px-2"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    {formatDate(dateMessages[0].createdAt)}
                  </span>
                  <div
                    className="flex-1 h-px"
                    style={{ background: "var(--bz-border)" }}
                  />
                </div>

                {/* Messages for this date */}
                <div className="space-y-3">
                  {dateMessages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      formatTime={formatTime}
                    />
                  ))}
                </div>
              </div>
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div
        className="flex-shrink-0 pt-4 border-t"
        style={{ borderColor: "var(--bz-border)" }}
      >
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
              "flex-1 px-4 py-3 rounded-xl border",
              "focus:outline-none focus:ring-2 focus:ring-[var(--bz-border-accent)]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
              color: "var(--tx-primary)",
            }}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!newMessage.trim() || isSending}
            size="icon"
            className="h-12 w-12 rounded-xl"
            aria-label={isSending ? "Sending message" : "Send message"}
          >
            {isSending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </Button>
        </div>
        <p
          className="text-xs mt-2 text-center"
          style={{ color: "var(--bz-text-3)" }}
        >
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
  const isFromTeam = message.direction === "team_to_client";
  const isUnread = isFromTeam && !message.readAt;

  return (
    <div
      className={cn("flex gap-2", isFromTeam ? "justify-start" : "justify-end")}
    >
      {/* Team Avatar */}
      {isFromTeam && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{
            background: "color-mix(in srgb, var(--bz-copper) 10%, transparent)",
          }}
        >
          <Users className="w-4 h-4" style={{ color: "var(--bz-copper)" }} />
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          "max-w-[80%] md:max-w-[70%] rounded-2xl px-4 py-2.5",
          isFromTeam ? "rounded-tl-sm border" : "rounded-tr-sm",
        )}
        style={
          isFromTeam
            ? {
                background: "var(--bz-card)",
                borderColor: "var(--bz-border)",
                // Unread: hairline copper ring. Read: GARUDA Day concept
                // .panel shadow (soft navy on paper, near-invisible on
                // dark — same precedent as portal process page).
                boxShadow: isUnread
                  ? "0 0 0 2px color-mix(in srgb, var(--bz-copper) 35%, transparent)"
                  : "0 14px 34px rgba(22, 33, 58, 0.07)",
              }
            : {
                background: "var(--bz-accent-warm)",
                color: "var(--bz-on-warm)",
              }
        }
      >
        {/* Sender name for team messages */}
        {isFromTeam && message.sentBy && (
          <p
            className="text-xs font-medium mb-1"
            style={{ color: "var(--bz-copper-text)" }}
          >
            {message.sentBy}
          </p>
        )}

        {/* Subject if present */}
        {message.subject && (
          <p
            className="text-sm font-semibold mb-1"
            style={{
              color: isFromTeam ? "var(--tx-primary)" : "var(--bz-on-warm)",
            }}
          >
            {message.subject}
          </p>
        )}

        {/* Message content */}
        <p
          className="text-sm whitespace-pre-wrap break-words"
          style={{
            color: isFromTeam ? "var(--tx-primary)" : "var(--bz-on-warm)",
          }}
        >
          {message.content}
        </p>

        {/* Time — full-strength fg on both bubble kinds: the previous
            60%-opacity ink measured 2.54:1 on daylight gold (AA fail);
            --bz-on-warm is 4.86:1 light / 8.43:1 dark. */}
        <p
          className="text-[10px] mt-1"
          style={{
            color: isFromTeam ? "var(--tx-secondary)" : "var(--bz-on-warm)",
          }}
        >
          {formatTime(message.createdAt)}
          {!isFromTeam && message.readAt && " • Read"}
        </p>
      </div>

      {/* User Avatar */}
      {!isFromTeam && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{ background: "var(--bz-accent-warm)" }}
        >
          <User className="w-4 h-4" style={{ color: "var(--bz-on-warm)" }} />
        </div>
      )}
    </div>
  );
}

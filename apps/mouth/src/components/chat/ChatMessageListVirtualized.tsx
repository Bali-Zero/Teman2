'use client';

import { RefObject, useRef, useCallback, useEffect, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { MessageBubble } from './MessageBubble';
import { ThinkingIndicator } from './ThinkingIndicator';
import { NewMessagesPill } from './NewMessagesPill';
import { ChatMessageListSkeleton } from '@/components/ui/skeleton';
import { Message } from '@/types';

export interface ChatMessageListVirtualizedProps {
  messages: Message[];
  isLoading: boolean;
  isInitialLoading?: boolean;
  thinkingElapsedTime: number;
  userAvatar: string | null;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  onFollowUpClick: (question: string) => void;
  onSetInput: (value: string) => void;
  onOpenSearchDocs: () => void;
}

// Estimated heights for virtualization
const ESTIMATED_MESSAGE_HEIGHT = 150;
const THRESHOLD_FOR_VIRTUALIZATION = 20;

/**
 * Virtualized chat message list for improved performance with large message histories.
 * Uses @tanstack/react-virtual for windowing.
 * Falls back to regular rendering for small message counts.
 */
export function ChatMessageListVirtualized({
  messages,
  isLoading,
  isInitialLoading = false,
  thinkingElapsedTime,
  userAvatar,
  messagesEndRef,
  onFollowUpClick,
  onSetInput,
  onOpenSearchDocs,
}: ChatMessageListVirtualizedProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  // Filter out empty assistant placeholders
  const filteredMessages = messages.filter((message, index) => {
    const isLastMessage = index === messages.length - 1;
    const isEmptyAssistantPlaceholder =
      message.role === 'assistant' && !message.content && isLastMessage && isLoading;
    return !isEmptyAssistantPlaceholder;
  });

  // Use virtualization only for large message counts
  const shouldVirtualize = filteredMessages.length > THRESHOLD_FOR_VIRTUALIZATION;

  const virtualizer = useVirtualizer({
    count: filteredMessages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_MESSAGE_HEIGHT,
    overscan: 5,
  });

  // Scroll-anchor state. We only auto-scroll while the user sits at (or near)
  // the bottom; if they scroll up to read history we honor that and surface a
  // "new messages" pill instead. The 100px tolerance absorbs minor jitter
  // from layout shifts during streaming.
  const SCROLL_ANCHOR_TOLERANCE_PX = 100;
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const lastSeenLengthRef = useRef(filteredMessages.length);

  const scrollToBottom = useCallback((force = false) => {
    requestAnimationFrame(() => {
      const el = parentRef.current;
      if (!el) return;
      el.scrollTop = el.scrollHeight;
      if (force) setIsAtBottom(true);
    });
  }, []);

  const handleScroll = useCallback(() => {
    const el = parentRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom < SCROLL_ANCHOR_TOLERANCE_PX;
    setIsAtBottom(atBottom);
    if (atBottom) setUnreadCount(0);
  }, []);

  // Reflect new content arrivals: scroll if anchored, otherwise just bump the
  // unread counter so the pill becomes useful.
  useEffect(() => {
    const newCount = filteredMessages.length;
    const grew = newCount > lastSeenLengthRef.current;
    lastSeenLengthRef.current = newCount;

    if (isAtBottom) {
      scrollToBottom();
      const t1 = setTimeout(() => scrollToBottom(), 50);
      const t2 = setTimeout(() => scrollToBottom(), 150);
      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }
    if (grew) {
      setUnreadCount((n) => n + (newCount - (lastSeenLengthRef.current - 1)));
    }
  }, [filteredMessages.length, scrollToBottom, thinkingElapsedTime, isLoading, isAtBottom]);

  const handlePillClick = useCallback(() => {
    setUnreadCount(0);
    scrollToBottom(true);
  }, [scrollToBottom]);

  // Initial loading state
  if (isInitialLoading) {
    return <ChatMessageListSkeleton count={3} />;
  }

  // Empty state (welcome screen)
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-4 min-h-0 relative z-10">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="relative mb-8"
        >
          <Image
            src="/assets/logo/logo_zan.png"
            alt="Zantara Logo"
            width={140}
            height={140}
            priority
            className="relative z-10 drop-shadow-[0_0_30px_rgba(100,100,255,0.3)] opacity-100"
          />
        </motion.div>

        <div className="space-y-4 text-center mb-12">
          <h1 className="text-2xl font-light tracking-[0.2em] text-white/90 uppercase">Zantara</h1>
          <div className="flex items-center justify-center gap-4">
            <div className="h-[1px] w-12 bg-gradient-to-r from-transparent to-white/30" />
            <p className="text-xs text-[var(--foreground-muted)] tracking-[0.4em] uppercase font-medium">
              Garda Depan Leluhur
            </p>
            <div className="h-[1px] w-12 bg-gradient-to-l from-transparent to-white/30" />
          </div>
        </div>

        {/* Quick Actions */}
        <div className="flex flex-wrap justify-center gap-3 mb-6">
          <Button
            variant="outline"
            size="lg"
            className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all focus-ring"
            onClick={() => onFollowUpClick?.('What can you help me with?')}
            aria-label="Ask what Zantara can do"
          >
            <span className="text-lg" aria-hidden="true">
              💡
            </span>
            <span>What can you do?</span>
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all focus-ring"
            onClick={() => onFollowUpClick?.('Summarize my tasks for today')}
            aria-label="Get task summary"
          >
            <span className="text-lg" aria-hidden="true">
              📋
            </span>
            <span>My Tasks</span>
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all focus-ring"
            onClick={onOpenSearchDocs}
            aria-label="Search documents"
          >
            <span className="text-lg" aria-hidden="true">
              🔍
            </span>
            <span>Search docs</span>
          </Button>
        </div>
      </div>
    );
  }

  // Virtualized rendering for large lists
  if (shouldVirtualize) {
    return (
      <div className="flex-1 min-h-0 relative">
        <div
          ref={parentRef}
          onScroll={handleScroll}
          className="flex-1 overflow-auto min-h-0 h-full"
          style={{ contain: 'strict' }}
          role="log"
          aria-label="Chat messages"
          aria-live="polite"
        >
          <div
            className="max-w-3xl mx-auto px-4 py-6 relative"
            style={{
              height: `${virtualizer.getTotalSize()}px`,
            }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const message = filteredMessages[virtualRow.index];
              const isLastMessage = virtualRow.index === filteredMessages.length - 1;

              return (
                <div
                  key={message.id || message.timestamp.getTime()}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                >
                  <MessageBubble
                    message={message}
                    userAvatar={userAvatar}
                    isLast={isLastMessage}
                    onFollowUpClick={onFollowUpClick}
                  />
                </div>
              );
            })}
          </div>

          {/* Thinking Indicator */}
          {isLoading && (
            <div className="max-w-3xl mx-auto px-4 pb-6">
              <ThinkingIndicator
                isVisible={isLoading}
                currentStatus={messages[messages.length - 1]?.currentStatus}
                steps={messages[messages.length - 1]?.steps}
                elapsedTime={thinkingElapsedTime}
              />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
        <NewMessagesPill show={!isAtBottom} unreadCount={unreadCount} onClick={handlePillClick} />
      </div>
    );
  }

  // Regular rendering for small lists
  return (
    <div className="flex-1 min-h-0 relative">
      <div
        ref={parentRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto min-h-0 h-full"
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
      >
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
          {filteredMessages.map((message, index) => {
            const isLastMessage = index === filteredMessages.length - 1;

            return (
              <MessageBubble
                key={message.id || message.timestamp.getTime()}
                message={message}
                userAvatar={userAvatar}
                isLast={isLastMessage}
                onFollowUpClick={onFollowUpClick}
              />
            );
          })}

          {/* Thinking Indicator */}
          {isLoading && (
            <ThinkingIndicator
              isVisible={isLoading}
              currentStatus={messages[messages.length - 1]?.currentStatus}
              steps={messages[messages.length - 1]?.steps}
              elapsedTime={thinkingElapsedTime}
            />
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>
      <NewMessagesPill show={!isAtBottom} unreadCount={unreadCount} onClick={handlePillClick} />
    </div>
  );
}

export default ChatMessageListVirtualized;

'use client';

import { RefObject } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { MessageBubble } from './MessageBubble';
import { ThinkingIndicator } from './ThinkingIndicator';
import { Message } from '@/types';

export interface ChatMessageListProps {
  messages: Message[];
  isLoading: boolean;
  thinkingElapsedTime: number;
  userAvatar: string | null;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  onFollowUpClick: (question: string) => void;
  onSetInput: (value: string) => void;
  onOpenSearchDocs: () => void;
}

export function ChatMessageList({
  messages,
  isLoading,
  thinkingElapsedTime,
  userAvatar,
  messagesEndRef,
  onFollowUpClick,
  onSetInput,
  onOpenSearchDocs,
}: ChatMessageListProps) {
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
            src="/images/logo_zan.png"
            alt="Zantara Logo"
            width={140}
            height={140}
            priority
            className="relative z-10 drop-shadow-[0_0_30px_rgba(100,100,255,0.3)] opacity-100"
          />
        </motion.div>

        <div className="space-y-4 text-center mb-12">
          <h1 className="text-2xl font-light tracking-[0.2em] text-white/90 uppercase">
            Zantara
          </h1>
          <div className="flex items-center justify-center gap-4">
            <div className="h-[1px] w-12 bg-gradient-to-r from-transparent to-white/30" />
            <p className="text-xs text-[var(--foreground-muted)] tracking-[0.4em] uppercase font-medium">
              Garda Depan Leluhur
            </p>
            <div className="h-[1px] w-12 bg-gradient-to-l from-transparent to-white/30" />
          </div>
        </div>

        {/* Quick Actions in Welcome */}
        <div className="flex flex-wrap justify-center gap-3 mb-6">
          <Button
            variant="outline"
            size="lg"
            className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all"
            onClick={() => onSetInput('What can you help me with?')}
          >
            <span className="text-lg">💡</span>
            <span>What can you do?</span>
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all"
            onClick={() => onSetInput('Summarize my tasks for today')}
          >
            <span className="text-lg">📋</span>
            <span>My Tasks</span>
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all"
            onClick={onOpenSearchDocs}
          >
            <span className="text-lg">🔍</span>
            <span>Search docs</span>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      {messages.map((message, index) => {
        const isLastMessage = index === messages.length - 1;
        const isEmptyAssistantPlaceholder =
          message.role === 'assistant' &&
          !message.content &&
          isLastMessage &&
          isLoading;

        if (isEmptyAssistantPlaceholder) {
          return null;
        }

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
  );
}

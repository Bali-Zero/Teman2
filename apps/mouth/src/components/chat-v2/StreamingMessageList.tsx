'use client';

import { memo, useRef, useEffect } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';
import { type ChatMessage, type Source } from '@/app/chat/actions';

interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

interface StreamingMessageListProps {
  messages: OptimisticMessage[];
  currentStatus: string;
  isStreaming: boolean;
  userAvatar?: string | null;
}

/**
 * Streaming Message List Component
 *
 * Optimizations:
 * - Memoized to prevent unnecessary re-renders
 * - Virtualization-ready structure
 * - Efficient streaming status display
 * - Smooth auto-scroll
 */
export const StreamingMessageList = memo(function StreamingMessageList({
  messages,
  currentStatus,
  isStreaming,
  userAvatar,
}: StreamingMessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages or streaming updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStatus]);

  if (messages.length === 0) {
    return <WelcomeScreen />;
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          currentStatus={currentStatus}
          userAvatar={userAvatar}
        />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
});

/**
 * Individual Message Bubble
 */
const MessageBubble = memo(function MessageBubble({
  message,
  currentStatus,
  userAvatar,
}: {
  message: OptimisticMessage;
  currentStatus: string;
  userAvatar?: string | null;
}) {
  const isUser = message.role === 'user';
  const isAssistantStreaming = message.role === 'assistant' && message.isStreaming;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in-0 slide-in-from-bottom-2 duration-300`}>
      {/* Avatar for assistant */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--primary)] to-[var(--secondary)] flex items-center justify-center mr-2 shrink-0">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-[var(--primary)] text-white'
            : 'bg-[var(--card)] border border-[var(--border)]'
        } ${message.isPending ? 'opacity-70' : ''}`}
      >
        {/* Streaming State */}
        {isAssistantStreaming && !message.content ? (
          <StreamingIndicator status={currentStatus} />
        ) : (
          <>
            {/* Message Content */}
            <MessageContent content={message.content} />

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <SourcesList sources={message.sources} />
            )}

            {/* Pending Indicator */}
            {message.isPending && !message.isStreaming && (
              <div className="flex items-center gap-1 mt-2 text-xs opacity-60">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Sending...</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* User Avatar */}
      {isUser && userAvatar && (
        <div className="w-8 h-8 rounded-full overflow-hidden ml-2 shrink-0">
          <img src={userAvatar} alt="You" className="w-full h-full object-cover" />
        </div>
      )}
    </div>
  );
});

/**
 * Streaming Status Indicator
 */
function StreamingIndicator({ status }: { status: string }) {
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="relative">
        <Loader2 className="w-4 h-4 animate-spin text-[var(--primary)]" />
        <div className="absolute inset-0 animate-ping">
          <div className="w-4 h-4 rounded-full bg-[var(--primary)] opacity-20" />
        </div>
      </div>
      <span className="text-sm text-[var(--muted)] animate-pulse">
        {status || 'Thinking...'}
      </span>
    </div>
  );
}

/**
 * Message Content with Markdown-lite rendering
 */
function MessageContent({ content }: { content: string }) {
  // Simple markdown rendering for code blocks and bold
  const parts = content.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);

  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, idx) => {
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code key={idx} className="px-1.5 py-0.5 bg-[var(--background)] rounded text-sm font-mono">
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={idx}>{part.slice(2, -2)}</strong>;
        }
        return part;
      })}
    </p>
  );
}

/**
 * Sources List
 */
function SourcesList({ sources }: { sources: Source[] }) {
  return (
    <div className="mt-3 pt-3 border-t border-[var(--border)]">
      <p className="text-xs text-[var(--muted)] mb-2 flex items-center gap-1">
        <CheckCircle2 className="w-3 h-3" />
        Sources ({sources.length})
      </p>
      <div className="flex flex-wrap gap-1.5">
        {sources.slice(0, 5).map((source, idx) => (
          <a
            key={idx}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs px-2 py-1 bg-[var(--background)] rounded-md hover:bg-[var(--primary)]/10 transition-colors truncate max-w-[150px]"
            title={source.title}
          >
            {source.title}
          </a>
        ))}
        {sources.length > 5 && (
          <span className="text-xs px-2 py-1 text-[var(--muted)]">
            +{sources.length - 5} more
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Welcome Screen
 */
function WelcomeScreen() {
  const quickActions = [
    { icon: '📊', label: 'Show sales report', query: 'Show me today sales report' },
    { icon: '👥', label: 'List top customers', query: 'Who are our top customers this month?' },
    { icon: '📈', label: 'Revenue trends', query: 'What are the revenue trends for Q4?' },
    { icon: '🔍', label: 'Search products', query: 'Search for product catalog' },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[var(--primary)] to-[var(--secondary)] flex items-center justify-center mb-6">
        <Sparkles className="w-10 h-10 text-white" />
      </div>

      <h2 className="text-2xl font-semibold mb-2">Welcome to Zantara</h2>
      <p className="text-[var(--muted)] mb-8 max-w-md">
        Your AI-powered business assistant. Ask me anything about your data, reports, or get quick insights.
      </p>

      <div className="grid grid-cols-2 gap-3 max-w-md w-full">
        {quickActions.map((action, idx) => (
          <button
            key={idx}
            className="flex items-center gap-2 px-4 py-3 bg-[var(--card)] border border-[var(--border)] rounded-xl hover:border-[var(--primary)] transition-colors text-left"
            onClick={() => {
              // This would be handled by the parent component
              console.log('Quick action:', action.query);
            }}
          >
            <span className="text-xl">{action.icon}</span>
            <span className="text-sm">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

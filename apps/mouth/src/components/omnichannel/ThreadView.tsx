'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AutoResizeTextarea } from '@/components/ui/auto-resize-textarea';
import {
  CHANNEL_COLORS,
  CHANNEL_LABELS,
  type Thread,
  type ThreadMessage,
} from '@/lib/api/omnichannel/omnichannel.types';

interface ThreadViewProps {
  thread: Thread | null;
  messages: ThreadMessage[];
  onSendMessage: (content: string, opts: { channel?: string; isNote?: boolean }) => void;
  onUpdateThread: (update: { status?: string; priority?: string }) => void;
}

export function ThreadView({ thread, messages, onSendMessage, onUpdateThread }: ThreadViewProps) {
  const [input, setInput] = useState('');
  const [isNote, setIsNote] = useState(false);
  const [replyChannel, setReplyChannel] = useState<string | undefined>();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  // Set default reply channel from thread
  useEffect(() => {
    if (thread?.channels.length) {
      setReplyChannel(thread.channels[0]);
    }
  }, [thread?.channels]);

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    onSendMessage(input.trim(), {
      channel: isNote ? undefined : replyChannel,
      isNote,
    });
    setInput('');
  }, [input, isNote, replyChannel, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  if (!thread) {
    return (
      <div className="flex-1 flex items-center justify-center text-[var(--foreground-muted)]">
        <div className="text-center">
          <div className="text-4xl mb-4">💬</div>
          <p className="text-lg font-medium">Select a conversation</p>
          <p className="text-sm mt-1">Choose a thread from the inbox to view messages</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--background)]">
        <div className="flex items-center gap-3">
          <div>
            <h3 className="font-semibold text-[var(--foreground)]">
              {thread.client_name || thread.subject || 'Unknown'}
            </h3>
            <div className="flex items-center gap-2 mt-0.5">
              {thread.channels.map((ch) => (
                <span
                  key={ch}
                  className="text-[10px] font-medium"
                  style={{ color: CHANNEL_COLORS[ch] || '#6B7280' }}
                >
                  {CHANNEL_LABELS[ch] || ch}
                </span>
              ))}
              <span className="text-[10px] text-[var(--foreground-muted)]">{thread.status}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {thread.status === 'open' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onUpdateThread({ status: 'resolved' })}
              className="text-xs h-7"
            >
              Resolve
            </Button>
          )}
          {thread.status === 'resolved' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onUpdateThread({ status: 'open' })}
              className="text-xs h-7"
            >
              Reopen
            </Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-4 space-y-3">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {messages.length === 0 && (
            <p className="text-center text-[var(--foreground-muted)] text-sm py-8">
              No messages yet
            </p>
          )}
        </div>
      </ScrollArea>

      {/* Composer */}
      <div className="border-t border-[var(--border)] p-3 bg-[var(--background)]">
        {/* Note/Reply toggle + channel selector */}
        <div className="flex items-center gap-2 mb-2">
          <button
            type="button"
            onClick={() => setIsNote(false)}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              !isNote
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)]'
            }`}
          >
            Reply
          </button>
          <button
            type="button"
            onClick={() => setIsNote(true)}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              isNote
                ? 'bg-yellow-500 text-black'
                : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)]'
            }`}
          >
            Internal Note
          </button>

          {!isNote && thread.channels.length > 1 && (
            <select
              value={replyChannel}
              onChange={(e) => setReplyChannel(e.target.value)}
              className="text-xs bg-[var(--background-secondary)] text-[var(--foreground)] border border-[var(--border)] rounded px-2 py-1"
            >
              {thread.channels.map((ch) => (
                <option key={ch} value={ch}>
                  via {CHANNEL_LABELS[ch] || ch}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Input */}
        <div className={`flex gap-2 ${isNote ? 'bg-yellow-500/10 rounded p-2' : ''}`}>
          <AutoResizeTextarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isNote ? 'Write an internal note...' : 'Type a reply...'}
            className="flex-1 text-sm bg-[var(--background-secondary)] resize-none min-h-[36px] max-h-[120px]"
          />
          <Button onClick={handleSend} disabled={!input.trim()} size="sm" className="self-end h-9">
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ThreadMessage }) {
  const isInbound = message.direction === 'inbound';
  const isInternal = message.direction === 'internal' || message.metadata?.is_internal_note;
  const senderName =
    (message.metadata?.sender_name as string) ||
    (message.metadata?.first_name as string) ||
    message.sender_id;

  return (
    <div
      className={`flex ${isInbound ? 'justify-start' : 'justify-end'} ${
        isInternal ? 'opacity-90' : ''
      }`}
    >
      <div
        className={`max-w-[75%] rounded-xl px-4 py-2.5 ${
          isInternal
            ? 'bg-yellow-500/15 border border-yellow-500/30'
            : isInbound
              ? 'bg-[var(--background-secondary)]'
              : 'bg-[var(--accent)]/15'
        }`}
      >
        {/* Channel badge + sender */}
        <div className="flex items-center gap-1.5 mb-1">
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{
              backgroundColor: CHANNEL_COLORS[message.channel] || '#6B7280',
            }}
          />
          <span className="text-[10px] font-medium text-[var(--foreground-muted)]">
            {isInternal ? 'Note' : CHANNEL_LABELS[message.channel] || message.channel}
            {' - '}
            {senderName}
          </span>
        </div>

        {/* Content */}
        <p className="text-sm text-[var(--foreground)] whitespace-pre-wrap break-words">
          {message.content}
        </p>

        {/* Timestamp */}
        <p className="text-[10px] text-[var(--foreground-muted)] mt-1 text-right">
          {message.created_at
            ? new Date(message.created_at).toLocaleTimeString('en-GB', {
                hour: '2-digit',
                minute: '2-digit',
              })
            : ''}
        </p>
      </div>
    </div>
  );
}

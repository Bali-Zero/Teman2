/**
 * ChatPanel — main chat container with message list + input.
 *
 * Pattern from V5: purely presentational, all logic in useChatPage.
 */

"use client";

import { useEffect, useRef } from "react";
import { ChatInput } from "@/components/molecules/ChatInput";
import { MessageBubble } from "@/components/organisms/MessageBubble";
import type { ChatMessage } from "@/hooks/useChatMessages";

interface ChatPanelProps {
  messages: ChatMessage[];
  currentNode: string;
  isLoading: boolean;
  error: string | null;
  onSend: (message: string) => void;
  onAbort: () => void;
}

export function ChatPanel({
  messages,
  currentNode,
  isLoading,
  error,
  onSend,
  onAbort,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentNode]);

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <WelcomeScreen />
        ) : (
          <div className="mx-auto max-w-3xl py-4">
            {messages.map((msg, i) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                isLast={i === messages.length - 1}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-auto max-w-3xl px-4 py-2">
          <div className="rounded-lg bg-error/10 px-3 py-2 text-sm text-error">
            {error}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="mx-auto w-full max-w-3xl px-4 pb-4">
        <ChatInput onSend={onSend} onAbort={onAbort} isLoading={isLoading} />
      </div>
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="text-4xl">🇮🇩</div>
      <h1 className="text-2xl font-semibold text-foreground">Nuzantara V6</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Ask about Indonesian business setup, visas, property acquisition, tax
        compliance, or KBLI codes.
      </p>
      <div className="flex flex-wrap justify-center gap-2 text-xs text-muted-foreground">
        {[
          "How to set up a PT PMA?",
          "KITAS requirements",
          "PPN VAT rate",
          "Buying property in Bali",
        ].map((q) => (
          <span
            key={q}
            className="cursor-default rounded-full border border-border px-3 py-1.5 hover:bg-muted"
          >
            {q}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * MessageBubble — user/assistant message with markdown and sources.
 *
 * Pattern from V5: typewriter animation via requestAnimationFrame.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot } from "lucide-react";
import { NodeProgress } from "@/components/molecules/NodeProgress";
import type { ChatMessage } from "@/hooks/useChatMessages";

interface MessageBubbleProps {
  message: ChatMessage;
  isLast?: boolean;
}

export function MessageBubble({ message, isLast = false }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [displayedContent, setDisplayedContent] = useState(message.content);
  const animFrameRef = useRef<number | null>(null);

  // Typewriter animation for new assistant messages
  useEffect(() => {
    if (isUser || message.isStreaming) {
      setDisplayedContent(message.content);
      return;
    }

    const isRecent = Date.now() - message.timestamp.getTime() < 10_000;
    if (!isLast || !isRecent || !message.content) {
      setDisplayedContent(message.content);
      return;
    }

    let idx = 0;
    const text = message.content;
    const charsPerFrame = text.length > 500 ? 5 : 2;

    const type = () => {
      idx = Math.min(idx + charsPerFrame, text.length);
      setDisplayedContent(text.slice(0, idx));
      if (idx < text.length) {
        animFrameRef.current = requestAnimationFrame(type);
      }
    };

    setDisplayedContent("");
    animFrameRef.current = requestAnimationFrame(type);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [message.content, message.isStreaming, isUser, isLast, message.timestamp]);

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-accent text-accent-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
          isUser
            ? "bg-accent text-accent-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {message.isStreaming && message.currentNode ? (
          <NodeProgress currentNode={message.currentNode} />
        ) : displayedContent ? (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {displayedContent}
            </ReactMarkdown>
          </div>
        ) : (
          <NodeProgress currentNode="pipeline" />
        )}

        {/* Sources */}
        {!message.isStreaming &&
          message.sources &&
          message.sources.length > 0 && (
            <div className="mt-2 border-t border-border/50 pt-2">
              <p className="text-xs font-medium text-muted-foreground">
                Sources:
              </p>
              <ul className="mt-1 space-y-0.5">
                {message.sources.slice(0, 5).map((src, i) => (
                  <li key={i} className="text-xs text-muted-foreground">
                    {(src.title as string) || `Source ${i + 1}`}
                  </li>
                ))}
              </ul>
            </div>
          )}
      </div>
    </div>
  );
}

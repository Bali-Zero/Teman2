/**
 * ChatInput — auto-growing textarea with send button.
 * Pattern from V5: Shift+Enter for newline, Enter to send.
 */

"use client";

import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { Send, Square } from "lucide-react";
import { Button } from "@/components/atoms/Button";

const MAX_TEXTAREA_HEIGHT = 120;

interface ChatInputProps {
  onSend: (message: string) => void;
  onAbort?: () => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  onAbort,
  isLoading = false,
  placeholder = "Ask about Indonesian business, visas, property, or tax...",
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, isLoading, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT) + "px";
  }, []);

  return (
    <div className="flex items-end gap-2 rounded-xl border border-border bg-background p-2">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        placeholder={placeholder}
        rows={1}
        className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
        disabled={isLoading}
      />
      {isLoading ? (
        <Button
          variant="ghost"
          onClick={onAbort}
          aria-label="Stop"
          className="h-9 w-9 p-0"
        >
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          onClick={handleSend}
          disabled={!value.trim()}
          aria-label="Send"
          className="h-9 w-9 p-0"
        >
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

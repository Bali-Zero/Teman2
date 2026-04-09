/**
 * TerminalInput — fixed prompt bar at the bottom of the terminal.
 *
 * Behaviour:
 *  - Monospace textarea grows from 1 to 6 rows as the user types.
 *  - Cmd/Ctrl+Enter submits (plain Enter = newline).
 *  - ArrowUp/ArrowDown navigate history when the caret sits at the
 *    first/last line respectively.
 *  - Escape cancels the current stream.
 *  - Disabled while streaming; a Stop button replaces Send.
 */

"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  type KeyboardEvent,
} from "react";
import { Send, Square } from "lucide-react";

interface TerminalInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  onHistoryNavigate: (direction: "up" | "down") => void;
  isStreaming: boolean;
  placeholder?: string;
}

export interface TerminalInputHandle {
  focus: () => void;
}

const MAX_ROWS = 6;
const LINE_HEIGHT = 22; // px, must match leading-[22px] below.

export const TerminalInput = forwardRef<TerminalInputHandle, TerminalInputProps>(
  function TerminalInput(
    {
      value,
      onChange,
      onSubmit,
      onCancel,
      onHistoryNavigate,
      isStreaming,
      placeholder = "Ask anything, or type a command...",
    },
    ref,
  ) {
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);

    useImperativeHandle(ref, () => ({
      focus: () => textareaRef.current?.focus(),
    }));

    // Auto-grow textarea up to MAX_ROWS.
    useLayoutEffect(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.style.height = "auto";
      const next = Math.min(el.scrollHeight, LINE_HEIGHT * MAX_ROWS + 16);
      el.style.height = `${next}px`;
    }, [value]);

    // Focus on mount (desktop).
    useEffect(() => {
      if (typeof window === "undefined") return;
      if (window.matchMedia("(pointer: fine)").matches) {
        textareaRef.current?.focus();
      }
    }, []);

    const handleKeyDown = useCallback(
      (e: KeyboardEvent<HTMLTextAreaElement>) => {
        // Enter: submit (Shift+Enter for newline).
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          if (!isStreaming && value.trim().length > 0) {
            onSubmit();
          }
          return;
        }
        // Escape: cancel ongoing stream.
        if (e.key === "Escape") {
          if (isStreaming) {
            e.preventDefault();
            onCancel();
          }
          return;
        }
        // Arrow history navigation (only at caret extremities).
        if (e.key === "ArrowUp" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
          const el = textareaRef.current;
          if (el && el.selectionStart === 0 && el.selectionEnd === 0) {
            e.preventDefault();
            onHistoryNavigate("up");
          }
          return;
        }
        if (e.key === "ArrowDown" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
          const el = textareaRef.current;
          if (el && el.selectionStart === el.value.length) {
            e.preventDefault();
            onHistoryNavigate("down");
          }
          return;
        }
      },
      [isStreaming, value, onSubmit, onCancel, onHistoryNavigate],
    );

    const canSubmit = !isStreaming && value.trim().length > 0;
    const charCount = value.length;

    return (
      <div className="relative border-t border-white/10 bg-[var(--bz-base)]/95 backdrop-blur-md">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) onSubmit();
          }}
          className="px-4 md:px-6 py-3"
        >
          <div
            className={`flex items-start gap-2 rounded-lg border bg-[var(--bz-elevated)]/70 px-3 py-2 transition-colors ${isStreaming ? "border-[var(--bz-accent)]/40" : "border-white/10 focus-within:border-[var(--bz-accent)]/60"}`}
          >
            <span
              className="font-mono text-[13px] text-[var(--bz-accent)] font-semibold pt-[3px] select-none"
              aria-hidden="true"
            >
              zantara&gt;
            </span>
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={isStreaming}
              rows={1}
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              aria-label="Terminal prompt input"
              className="flex-1 resize-none bg-transparent font-mono text-[13px] leading-[22px] text-white/95 placeholder:text-white/30 focus:outline-none disabled:opacity-60"
              style={{ maxHeight: `${LINE_HEIGHT * MAX_ROWS + 16}px` }}
            />
            {isStreaming ? (
              <button
                type="button"
                onClick={onCancel}
                className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-[var(--bz-red)]/20 border border-[var(--bz-red)]/40 text-[var(--bz-red)] hover:bg-[var(--bz-red)]/30 transition-colors"
                aria-label="Cancel stream (Escape)"
                title="Stop (Esc)"
              >
                <Square size={11} />
                <span className="font-mono text-[10.5px] uppercase tracking-[0.5px]">
                  stop
                </span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!canSubmit}
                className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-[var(--bz-accent)]/90 hover:bg-[var(--bz-accent)] disabled:opacity-30 disabled:cursor-not-allowed text-white transition-colors"
                aria-label="Send message (Enter)"
                title="Send (Enter)"
              >
                <Send size={11} />
                <span className="font-mono text-[10.5px] uppercase tracking-[0.5px]">
                  send
                </span>
              </button>
            )}
          </div>
          <div className="mt-1 flex items-center justify-between px-1">
            <div className="font-mono text-[9.5px] text-white/30 uppercase tracking-[0.5px]">
              {isStreaming
                ? "streaming · esc to stop"
                : "enter to send · shift+enter newline · ↑↓ history"}
            </div>
            <div className="font-mono text-[9.5px] text-white/30 tabular-nums">
              {charCount} chars
            </div>
          </div>
        </form>
      </div>
    );
  },
);

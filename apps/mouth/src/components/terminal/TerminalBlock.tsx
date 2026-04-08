/**
 * TerminalBlock — a single card in the terminal timeline.
 *
 * Two visual variants driven by `role`:
 *   - user: right-aligned, copper-bordered prompt card, mono content.
 *   - assistant: left-aligned, subtle border, markdown-rendered content
 *     with inline tool-call pills and metadata footer.
 *
 * A copy button appears on hover (top-right). The entire block fades in
 * once on mount via framer-motion.
 */

"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Check, Copy } from "lucide-react";
import type { TerminalBlock as TerminalBlockType } from "./types";
import { TerminalMarkdown } from "./TerminalMarkdown";
import { TerminalToolCall } from "./TerminalToolCall";

interface TerminalBlockProps {
  block: TerminalBlockType;
  isActive?: boolean;
}

function formatTimestamp(ts: number): string {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function formatLatency(ms?: number): string | null {
  if (ms === undefined || ms < 0) return null;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function TerminalBlock({ block, isActive = false }: TerminalBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(block.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API blocked — silently ignore.
    }
  };

  const isUser = block.role === "user";
  const isStreaming = block.status === "streaming";
  const isError = block.status === "error";
  const isCancelled = block.status === "cancelled";

  const borderClass = isUser
    ? "border-[var(--bz-accent)]/45"
    : isError
      ? "border-[var(--bz-red)]/50"
      : isCancelled
        ? "border-white/20"
        : "border-white/10";

  const timestampStr = formatTimestamp(block.timestamp);
  const latencyStr = formatLatency(block.latencyMs);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`relative group ${isUser ? "max-w-[85%] md:max-w-[75%]" : "w-full md:max-w-[92%]"}`}
      >
        <div
          className={`relative rounded-lg border ${borderClass} bg-[var(--bz-elevated)]/90 backdrop-blur-sm shadow-[0_2px_12px_rgba(0,0,0,0.25)] px-3 py-3 ${isActive && isStreaming ? "ring-1 ring-[var(--bz-accent)]/30" : ""}`}
        >
          {/* Prompt prefix for user blocks */}
          {isUser && (
            <div className="flex items-start gap-2 font-mono text-[13px] text-white/90 whitespace-pre-wrap break-words">
              <span className="text-[var(--bz-accent)] font-semibold select-none">
                zantara&gt;
              </span>
              <span className="flex-1">{block.content}</span>
            </div>
          )}

          {/* Assistant content */}
          {!isUser && (
            <div className="space-y-2">
              {block.toolCalls.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {block.toolCalls.map((tc, idx) => (
                    <TerminalToolCall key={`${tc.name}-${idx}`} toolCall={tc} />
                  ))}
                </div>
              )}
              {block.content ? (
                <TerminalMarkdown>{block.content}</TerminalMarkdown>
              ) : isStreaming ? (
                <div className="flex items-center gap-1 text-white/40 text-[12px] font-mono">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--bz-accent)] animate-pulse" />
                  thinking
                </div>
              ) : null}
              {isStreaming && block.content && (
                <span
                  className="inline-block w-[6px] h-[14px] bg-[var(--bz-accent)] animate-pulse rounded-sm align-middle"
                  aria-hidden="true"
                />
              )}
            </div>
          )}

          {/* Copy button (hover) */}
          {block.content && (
            <button
              type="button"
              onClick={handleCopy}
              className="absolute top-1.5 right-1.5 p-1 rounded-md bg-black/40 border border-white/10 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/60"
              aria-label="Copy block content"
              title="Copy"
            >
              {copied ? (
                <Check size={11} className="text-[var(--bz-green)]" />
              ) : (
                <Copy size={11} className="text-white/60" />
              )}
            </button>
          )}

          {/* Footer metadata */}
          <div className="mt-2 pt-1.5 border-t border-white/5 flex items-center gap-3 text-[9.5px] font-mono uppercase tracking-[0.5px] text-white/35">
            <span>{timestampStr}</span>
            {!isUser && latencyStr && <span>· {latencyStr}</span>}
            {block.tokenCount !== undefined && (
              <span>· {block.tokenCount} tok</span>
            )}
            {!isUser && block.model && <span>· {block.model}</span>}
            {isError && (
              <span className="text-[var(--bz-red)]">· error</span>
            )}
            {isCancelled && (
              <span className="text-white/50">· cancelled</span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

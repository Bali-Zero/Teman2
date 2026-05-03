/**
 * Terminal — full-page orchestrator for the Zantara Terminal.
 *
 * Composes:
 *   - TerminalStatusBar (top)
 *   - Scrollable block list (TerminalBlock) with TerminalWelcome empty state
 *   - TerminalInput (bottom)
 *
 * Wires the useTerminal hook to user profile + gateway, auto-scrolls on new
 * blocks, and consumes any pending widget handoff from localStorage.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { UserProfile } from "@/types";
import { TerminalBlock } from "./TerminalBlock";
import { TerminalInput, type TerminalInputHandle } from "./TerminalInput";
import { TerminalStatusBar } from "./TerminalStatusBar";
import { TerminalWelcome } from "./TerminalWelcome";
import { useTerminal } from "./useTerminal";
import { TERMINAL_HANDOFF_KEY, type TerminalHandoff } from "./types";

export function Terminal() {
  const pathname = usePathname();
  const inputHandle = useRef<TerminalInputHandle | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const profile = api.getUserProfile() as UserProfile | null;
  const userName = profile?.name || profile?.email?.split("@")[0] || "Team";
  const userEmail = profile?.email || "anonymous";
  const userRole = profile?.role || "member";

  const sessionId = useMemo(
    () => `term_${userEmail.replace(/[^a-zA-Z0-9]/g, "_")}`,
    [userEmail],
  );

  const {
    blocks,
    input,
    setInput,
    isStreaming,
    sendMessage,
    cancelStream,
    history,
    historyIndex,
    navigateHistory,
    seedFromHandoff,
  } = useTerminal({
    sessionId,
    workspacePage: pathname ?? "/terminal",
  });

  void history;
  void historyIndex;

  // Consume any pending handoff from the floating widget on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(TERMINAL_HANDOFF_KEY);
      if (!raw) return;
      window.localStorage.removeItem(TERMINAL_HANDOFF_KEY);
      const parsed = JSON.parse(raw) as TerminalHandoff;
      if (parsed && Array.isArray(parsed.history) && parsed.history.length > 0) {
        seedFromHandoff(parsed.history);
      }
    } catch {
      // ignore bad payload
    }
  }, [seedFromHandoff]);

  // Auto-scroll to bottom on new blocks / streaming.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [blocks]);

  // Global Escape to cancel (even if input not focused).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isStreaming) {
        e.preventDefault();
        cancelStream();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isStreaming, cancelStream]);

  const handleSelectSuggestion = useCallback(
    (text: string) => {
      void sendMessage(text);
      inputHandle.current?.focus();
    },
    [sendMessage],
  );

  // Compute the most recent model / tokens for the status bar.
  const lastAssistant = [...blocks].reverse().find((b) => b.role === "assistant");
  const totalTokens = blocks.reduce((sum, b) => sum + (b.tokenCount ?? 0), 0);

  return (
    <div
      className="flex flex-col h-[calc(100vh-var(--bz-header-height,48px))] md:h-[calc(100vh-var(--bz-header-height,48px))] bg-[var(--bz-base)] text-white"
      data-zantara-terminal=""
    >
      <TerminalStatusBar
        model={lastAssistant?.model}
        role={userRole}
        tokenCount={totalTokens}
        sessionId={sessionId}
      />

      {/* Blocks area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 md:px-6 py-5 terminal-scrollbar"
        role="log"
        aria-live="polite"
        aria-label="Terminal output"
      >
        {blocks.length === 0 ? (
          <TerminalWelcome
            userName={userName}
            onSelectSuggestion={handleSelectSuggestion}
          />
        ) : (
          <div className="flex flex-col gap-4 max-w-5xl mx-auto pb-4">
            {blocks.map((block, idx) => (
              <TerminalBlock
                key={block.id}
                block={block}
                isActive={idx === blocks.length - 1}
              />
            ))}
          </div>
        )}
      </div>

      <TerminalInput
        ref={inputHandle}
        value={input}
        onChange={setInput}
        onSubmit={() => void sendMessage()}
        onCancel={cancelStream}
        onHistoryNavigate={navigateHistory}
        isStreaming={isStreaming}
      />

      {/* Scrollbar + prose tweaks — scoped via data attribute */}
      <style jsx global>{`
        [data-zantara-terminal] .terminal-scrollbar::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        [data-zantara-terminal] .terminal-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        [data-zantara-terminal] .terminal-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.08);
          border-radius: 4px;
        }
        [data-zantara-terminal] .terminal-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.16);
        }
        [data-zantara-terminal] .terminal-md {
          font-family:
            "JetBrains Mono",
            "IBM Plex Mono",
            ui-monospace,
            SFMono-Regular,
            Menlo,
            Monaco,
            Consolas,
            monospace;
        }
      `}</style>
    </div>
  );
}

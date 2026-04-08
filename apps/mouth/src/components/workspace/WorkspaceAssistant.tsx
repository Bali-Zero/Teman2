/**
 * WorkspaceAssistant - AI chat for team members inside the workspace.
 *
 * Floating button (bottom-right) → opens chat panel.
 * Authenticated via httpOnly cookie. Context-aware (knows user role + current page).
 * Uses same SSE streaming as ZantaraWidget but with team member identity.
 */

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageCircle,
  X,
  Send,
  Loader2,
  SquareArrowOutUpRight,
} from "lucide-react";
import dynamic from "next/dynamic";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });
import { api } from "@/lib/api";
import { sendChat } from "@/lib/gateway";
import { TERMINAL_HANDOFF_KEY } from "@/components/terminal/types";

// ── Types ──────────────────────────────────────────────────────────────

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

const genId = () =>
  `wa_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

// ── Component ──────────────────────────────────────────────────────────

export function WorkspaceAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pathname = usePathname();

  // Get user profile from API client cache
  const profile = api.getUserProfile();
  const userName = profile?.name || profile?.email?.split("@")[0] || "Team";
  const userEmail = profile?.email || "";
  const userRole = profile?.role || "member";

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // Keyboard shortcut: Cmd+J to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "j") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Send message
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");

    const userMsg: ChatMsg = { id: genId(), role: "user", content: text };
    const assistantMsg: ChatMsg = {
      id: genId(),
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    try {
      const history = messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({ role: m.role, content: m.content }));

      // Workspace agent endpoint: auth required, agent identity derived
      // server-side from JWT. We do NOT send agent_email / agent_name /
      // agent_role here — the backend resolves them from the cookie JWT
      // via team_agent_config so they cannot be spoofed by the client.
      // The backend also forces channel="workspace" server-side.
      const res = await sendChat({
        query: text,
        session_id: `ws_${userEmail.replace("@", "_")}`,
        conversation_history: history,
        workspace_page: pathname,
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") continue;

          try {
            const parsed = JSON.parse(data);
            if (parsed.type === "token" && typeof parsed.data === "string") {
              accumulated += parsed.data;
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last?.role !== "assistant") return prev;
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: accumulated },
                ];
              });
            }
          } catch {
            // Skip unparseable lines
          }
        }
      }

      // Finalize
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role !== "assistant") return prev;
        return [
          ...prev.slice(0, -1),
          {
            ...last,
            content: accumulated || "Maaf, ada masalah koneksi. Coba lagi.",
            isStreaming: false,
          },
        ];
      });
    } catch {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role !== "assistant") return prev;
        return [
          ...prev.slice(0, -1),
          {
            ...last,
            content: "Koneksi bermasalah. Silakan coba lagi.",
            isStreaming: false,
          },
        ];
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, messages, userEmail, pathname]);

  // Persist the current conversation to localStorage so that the full
  // `/terminal` page can seed its block list on mount. We strip any
  // in-progress streaming message to avoid transferring partial content.
  const handleOpenInTerminal = useCallback(() => {
    if (typeof window === "undefined") return;
    try {
      const history = messages
        .filter((m) => !m.isStreaming && m.content.trim().length > 0)
        .map((m) => ({ role: m.role, content: m.content }));
      window.localStorage.setItem(
        TERMINAL_HANDOFF_KEY,
        JSON.stringify({ history, createdAt: Date.now() }),
      );
    } catch {
      // Quota or serialization failure — ignore, terminal will start fresh.
    }
    setOpen(false);
  }, [messages]);

  // Don't render for clients (portal users)
  if (userRole === "client") return null;

  return (
    <>
      {/* Chat Panel */}
      {open && (
        <div
          className="fixed bottom-20 right-4 sm:right-6 z-50 w-[400px] max-w-[calc(100vw-2rem)] h-[540px] max-h-[75vh] flex flex-col rounded-2xl bg-[var(--bz-surface,#111)] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Zantara Assistant"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[var(--bz-base,#0c0c0e)]">
            <div className="flex items-center gap-2.5">
              <Image
                src="/assets/logo/zantara-lotus.png"
                alt="Zantara"
                width={28}
                height={28}
                className="w-7 h-7"
              />
              <div>
                <p className="text-sm font-medium text-white">Zantara</p>
                <p className="text-[10px] text-white/40">
                  Assistant for {userName} &middot; Cmd+J
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Link
                href="/terminal"
                onClick={handleOpenInTerminal}
                className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                aria-label="Open in terminal"
                title="Open in terminal"
              >
                <SquareArrowOutUpRight className="w-4 h-4 text-white/50" />
              </Link>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                aria-label="Close assistant"
              >
                <X className="w-4 h-4 text-white/50" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 py-3 space-y-3"
          >
            {messages.length === 0 && (
              <div className="text-center py-8 text-white/30 text-sm">
                <p>Halo {userName}! Tanya apa saja.</p>
                <p className="mt-1 text-xs text-white/20">
                  Contoh: &quot;klien saya yang expire bulan ini&quot;
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-3.5 py-2 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-[var(--bz-accent,#d4845a)] text-white"
                      : "bg-white/5 text-white/90 border border-white/5"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => (
                          <p className="mb-1.5 last:mb-0">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc ml-4 mb-1.5">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal ml-4 mb-1.5">
                            {children}
                          </ol>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-white">
                            {children}
                          </strong>
                        ),
                        code: ({ children }) => (
                          <code className="bg-white/10 px-1 py-0.5 rounded text-xs">
                            {children}
                          </code>
                        ),
                      }}
                    >
                      {msg.content || (msg.isStreaming ? "..." : "")}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                  {msg.isStreaming && msg.content && (
                    <span className="inline-block w-1.5 h-4 bg-[var(--bz-accent,#d4845a)] animate-pulse ml-0.5 rounded-sm" />
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Input */}
          <div className="px-3 py-2.5 border-t border-white/10 bg-[var(--bz-base,#0c0c0e)]">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Tanya Zantara..."
                disabled={isStreaming}
                className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[var(--bz-accent,#d4845a)] disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isStreaming || !input.trim()}
                className="p-2 rounded-lg bg-[var(--bz-accent,#d4845a)] hover:bg-[var(--bz-accent,#d4845a)]/80 disabled:opacity-30 transition-all"
                aria-label="Send message"
              >
                {isStreaming ? (
                  <Loader2 className="w-4 h-4 text-white animate-spin" />
                ) : (
                  <Send className="w-4 h-4 text-white" />
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Floating Button */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className={`fixed bottom-4 right-4 sm:right-6 z-50 w-12 h-12 rounded-full shadow-lg shadow-black/30 flex items-center justify-center transition-all duration-200 ${
          open
            ? "bg-white/10 border border-white/20"
            : "bg-[var(--bz-accent,#d4845a)] hover:scale-105"
        }`}
        aria-label={open ? "Close Zantara" : "Open Zantara (Cmd+J)"}
        title="Cmd+J"
      >
        {open ? (
          <X className="w-5 h-5 text-white/70" />
        ) : (
          <MessageCircle className="w-5 h-5 text-white" />
        )}
      </button>
    </>
  );
}

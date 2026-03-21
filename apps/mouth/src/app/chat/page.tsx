/**
 * Chat Workspace — Clean rewrite
 *
 * iMessage-style: messages scroll, input at bottom, minimal sidebar.
 * Reuses existing API layer (api.sendMessageStreaming, conversations).
 * ~450 lines replacing 3,291 lines of over-engineering.
 */

"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Plus,
  Loader2,
  Menu,
  X,
  Trash2,
  Clock,
  LogOut,
  ChevronDown,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ConversationListItem } from "@/lib/api";
import { logger } from "@/lib/logger";

// ── Types ──────────────────────────────────────────────────────────────

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

const genId = () => `m_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
const genSession = () =>
  `session-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;

// ── Session persistence ────────────────────────────────────────────────

function getOrCreateSession(): string {
  if (typeof window === "undefined") return genSession();
  try {
    const stored = sessionStorage.getItem("z_sid");
    const expiry = sessionStorage.getItem("z_sid_exp");
    if (stored && expiry && Date.now() < parseInt(expiry, 10)) return stored;
    const sid = genSession();
    sessionStorage.setItem("z_sid", sid);
    sessionStorage.setItem("z_sid_exp", String(Date.now() + 86400000));
    return sid;
  } catch {
    return genSession();
  }
}

// ── Main Component ─────────────────────────────────────────────────────

export default function ChatPage() {
  const router = useRouter();

  // Core state
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<ConversationListItem[]>(
    [],
  );
  const [currentConvId, setCurrentConvId] = useState<number | null>(null);
  const [userName, setUserName] = useState("User");
  const [isClockIn, setIsClockIn] = useState(false);
  const [clockLoading, setClockLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  // Refs
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // ── Init ──────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push("/login");
      return;
    }

    const sid = getOrCreateSession();
    setSessionId(sid);

    // Load profile, conversations, clock status in parallel
    Promise.all([
      Promise.resolve().then(() => {
        const p = api.getUserProfile();
        if (p) setUserName(p.name || p.email?.split("@")[0] || "User");
      }),
      api
        .listConversations(20, 0)
        .then((r) => setConversations(r.conversations || []))
        .catch(() => {}),
      api
        .getClockStatus()
        .then((s) => setIsClockIn(s.is_clocked_in))
        .catch(() => {}),
      api
        .getConversationHistory(sid)
        .then((h) => {
          if (h.success && h.messages.length > 0) {
            setMessages(
              h.messages.map((m) => ({
                id: genId(),
                role: m.role as "user" | "assistant",
                content: m.content,
                timestamp: new Date(),
              })),
            );
          }
        })
        .catch(() => {}),
    ]).finally(() => setReady(true));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Auto-scroll ───────────────────────────────────────────────────────

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Track scroll position for "scroll to bottom" button
  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setShowScrollBtn(!nearBottom && messages.length > 5);
  }, [messages.length]);

  // ── Send message ──────────────────────────────────────────────────────

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setInput("");
    setError(null);

    const userMsg: ChatMsg = {
      id: genId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    const assistantMsg: ChatMsg = {
      id: genId(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const abortController = new AbortController();
    abortRef.current = abortController;

    const history = messages
      .filter((m) => !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      await api.sendMessageStreaming(
        text,
        sessionId || undefined,
        // onChunk
        (chunk: string) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role !== "assistant") return prev;
            return [...prev.slice(0, -1), { ...last, content: chunk }];
          });
        },
        // onDone
        (fullResponse: string) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role !== "assistant") return prev;
            return [
              ...prev.slice(0, -1),
              { ...last, content: fullResponse, isStreaming: false },
            ];
          });
          setIsStreaming(false);
          abortRef.current = null;
        },
        // onError
        (err: Error) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role !== "assistant") return prev;
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                content: "Sorry, something went wrong. Please try again.",
                isStreaming: false,
              },
            ];
          });
          setIsStreaming(false);
          setError(err.message);
          abortRef.current = null;
        },
        // onStep (unused — keep it simple)
        () => {},
        // timeoutMs
        120000,
        // conversationHistory
        history,
        // abortSignal
        abortController.signal,
        // correlationId
        undefined,
        // idleTimeoutMs
        300000,
        // maxTotalTimeMs
        600000,
      );
    } catch (err) {
      setIsStreaming(false);
      setError(err instanceof Error ? err.message : "Unknown error");
      abortRef.current = null;
    }
  }, [input, isStreaming, sessionId, messages]);

  // ── Keyboard ──────────────────────────────────────────────────────────

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // ── New chat ──────────────────────────────────────────────────────────

  const newChat = useCallback(() => {
    const sid = genSession();
    setSessionId(sid);
    setMessages([]);
    setCurrentConvId(null);
    setError(null);
    setSidebarOpen(false);
    try {
      sessionStorage.setItem("z_sid", sid);
      sessionStorage.setItem("z_sid_exp", String(Date.now() + 86400000));
    } catch {}
    inputRef.current?.focus();
  }, []);

  // ── Load conversation ─────────────────────────────────────────────────

  const loadConversation = useCallback(async (id: number) => {
    setCurrentConvId(id);
    try {
      const conv = await api.getConversation(id);
      if (conv?.messages) {
        setMessages(
          conv.messages
            .filter(
              (m): m is { role: string; content: string } =>
                typeof m.role === "string" && typeof m.content === "string",
            )
            .map((m) => ({
              id: genId(),
              role: (m.role === "user" ? "user" : "assistant") as
                | "user"
                | "assistant",
              content: m.content,
              timestamp: new Date(),
            })),
        );
        if (conv.session_id) {
          setSessionId(conv.session_id);
          try {
            sessionStorage.setItem("z_sid", conv.session_id);
          } catch {}
        }
      }
    } catch (err) {
      logger.error(
        "Failed to load conversation",
        { component: "ChatPage" },
        err instanceof Error ? err : new Error(String(err)),
      );
    }
    if (window.innerWidth < 768) setSidebarOpen(false);
  }, []);

  // ── Delete conversation ───────────────────────────────────────────────

  const deleteConversation = useCallback(
    async (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!confirm("Delete this conversation?")) return;
      try {
        await api.deleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (currentConvId === id) newChat();
      } catch {}
    },
    [currentConvId, newChat],
  );

  // ── Clock toggle ──────────────────────────────────────────────────────

  const toggleClock = useCallback(async () => {
    if (clockLoading) return;
    setClockLoading(true);
    try {
      const result = isClockIn ? await api.clockOut() : await api.clockIn();
      if (result.success) setIsClockIn(!isClockIn);
    } catch {}
    setClockLoading(false);
  }, [isClockIn, clockLoading]);

  // ── Loading screen ────────────────────────────────────────────────────

  if (!ready) {
    return (
      <div className="flex h-screen bg-[#1a1a1a] text-white items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-white/40" />
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen bg-[#1a1a1a] text-white overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-72 bg-[#141414] border-r border-white/5
          transform transition-transform duration-200 ease-out
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          md:relative md:translate-x-0 md:flex md:flex-col
          ${!sidebarOpen ? "md:hidden lg:flex" : ""}
        `}
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          <span className="text-sm font-medium text-white/70">
            Conversations
          </span>
          <button
            onClick={newChat}
            className="p-1.5 rounded-md hover:bg-white/10 text-white/50 hover:text-white transition-colors"
            title="New chat"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <p className="text-white/30 text-xs text-center mt-8">
              No conversations yet
            </p>
          ) : (
            conversations.slice(0, 20).map((conv) => (
              <div
                key={conv.id}
                onClick={() => loadConversation(conv.id)}
                className={`
                  group flex items-center px-4 py-3 cursor-pointer
                  border-b border-white/[0.03] transition-colors
                  ${currentConvId === conv.id ? "bg-white/10" : "hover:bg-white/5"}
                `}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white/80 truncate">
                    {conv.title || conv.preview || "Untitled"}
                  </p>
                  <p className="text-xs text-white/30 mt-0.5">
                    {conv.message_count} messages
                  </p>
                </div>
                <button
                  onClick={(e) => deleteConversation(conv.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 text-white/30 hover:text-red-400 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Sidebar footer: user + clock */}
        <div className="border-t border-white/5 p-3 space-y-2">
          <button
            onClick={toggleClock}
            disabled={clockLoading}
            className={`
              w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs
              transition-colors
              ${isClockIn ? "bg-green-500/10 text-green-400 hover:bg-green-500/20" : "bg-white/5 text-white/40 hover:bg-white/10"}
            `}
          >
            <Clock className="w-3.5 h-3.5" />
            {clockLoading ? "..." : isClockIn ? "Clocked In" : "Clock In"}
          </button>
          <div className="flex items-center justify-between px-1">
            <span className="text-xs text-white/40 truncate">{userName}</span>
            <button
              onClick={() => {
                api.logout();
                router.push("/login");
              }}
              className="p-1 rounded hover:bg-white/10 text-white/30 hover:text-white/60 transition-colors"
              title="Logout"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Sidebar overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Main area ───────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#1a1a1a]">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-md hover:bg-white/10 text-white/50 transition-colors"
            >
              {sidebarOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
            <h1 className="text-sm font-medium text-white/70">Zantara</h1>
          </div>
          {isClockIn && (
            <span className="text-xs text-green-400/60 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              Online
            </span>
          )}
        </header>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-4 py-6"
        >
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
                <span className="text-2xl">Z</span>
              </div>
              <p className="text-white/40 text-sm">
                Ask anything about visa, company setup, tax, or property in
                Indonesia.
              </p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={() =>
              bottomRef.current?.scrollIntoView({ behavior: "smooth" })
            }
            className="absolute bottom-24 left-1/2 -translate-x-1/2 z-10 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white/60 backdrop-blur-sm transition-all"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        )}

        {/* Error banner */}
        {error && (
          <div className="mx-4 mb-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-white/5 bg-[#1a1a1a] p-4">
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              send();
            }}
            className="max-w-3xl mx-auto flex items-end gap-2"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Zantara..."
              rows={1}
              className="
                flex-1 resize-none rounded-xl px-4 py-3 bg-white/5
                border border-white/10 text-sm text-white
                placeholder:text-white/25 focus:outline-none focus:border-white/20
                max-h-32 transition-colors
              "
              style={{
                height: "auto",
                minHeight: "44px",
              }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 128) + "px";
              }}
              disabled={isStreaming}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="
                p-3 rounded-xl transition-all
                disabled:opacity-20 disabled:cursor-not-allowed
                bg-white/10 hover:bg-white/15 text-white
              "
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

// ── Message Bubble ──────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`
          max-w-[85%] rounded-2xl px-4 py-3
          ${isUser ? "bg-blue-600 text-white" : "bg-white/[0.06] text-white/90"}
          ${msg.isStreaming && !msg.content ? "animate-pulse" : ""}
        `}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
        ) : msg.content ? (
          <div className="text-sm prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="flex gap-1 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce [animation-delay:300ms]" />
          </div>
        )}
        {msg.isStreaming && msg.content && (
          <span className="inline-block w-1.5 h-4 bg-white/40 animate-pulse ml-0.5 align-text-bottom" />
        )}
      </div>
    </div>
  );
}

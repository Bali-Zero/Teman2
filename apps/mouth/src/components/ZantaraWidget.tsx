/**
 * ZantaraWidget - Floating chat widget for public balizero.com pages
 *
 * Lightweight, anonymous, context-aware mini-chat.
 * After a few exchanges, Zantara naturally asks for contact info
 * and creates a CRM lead via POST /api/crm/clients.
 *
 * Uses the same SSE streaming backend as workspace chat.
 */

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import { MessageCircle, X, Send, Loader2 } from "lucide-react";
import dynamic from "next/dynamic";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

// ── Types ──────────────────────────────────────────────────────────────

interface WidgetMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

const genId = () => `w_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

// ── Visitor session ────────────────────────────────────────────────────

function getVisitorSession(): string {
  if (typeof window === "undefined") return genId();
  try {
    const stored = localStorage.getItem("z_visitor");
    if (stored) return stored;
    const sid = `visitor_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem("z_visitor", sid);
    return sid;
  } catch {
    return genId();
  }
}

// ── Context-aware greeting based on current page ───────────────────────

function getGreeting(path: string): string {
  if (
    path.includes("/services") ||
    path.includes("/visa") ||
    path.includes("/company")
  )
    return "Hi! Looking for info on visa, company setup, or tax in Bali? I can help.";
  if (path.includes("/kbli"))
    return "Hi! I can help you understand KBLI business codes for Indonesia.";
  if (path.includes("/immigration"))
    return "Hi! Have questions about visas or immigration in Indonesia?";
  if (path.includes("/property"))
    return "Hi! Interested in property or real estate in Bali?";
  if (path.includes("/tax"))
    return "Hi! Need help with tax or compliance in Indonesia?";
  if (path.includes("/contact"))
    return "Hi! Want to chat before reaching out? Ask me anything.";
  return "Hi! I'm Zantara from Bali Zero. Ask me anything about doing business or living in Bali.";
}

// ── Backend URL ────────────────────────────────────────────────────────

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev";

// ── Widget Component ───────────────────────────────────────────────────

export function ZantaraWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<WidgetMsg[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [hasGreeted, setHasGreeted] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionId = useRef(getVisitorSession());

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // Greet on first open
  const handleOpen = useCallback(() => {
    setOpen(true);
    if (!hasGreeted) {
      const path =
        typeof window !== "undefined" ? window.location.pathname : "";
      setMessages([
        {
          id: genId(),
          role: "assistant",
          content: getGreeting(path),
        },
      ]);
      setHasGreeted(true);
    }
  }, [hasGreeted]);

  // ── Send message ──────────────────────────────────────────────────

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setInput("");

    const userMsg: WidgetMsg = { id: genId(), role: "user", content: text };
    const assistantMsg: WidgetMsg = {
      id: genId(),
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    try {
      // Build conversation history
      const history = messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await fetch(`${BACKEND}/api/agentic-rag/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          user_id: sessionId.current,
          session_id: sessionId.current,
          enable_vision: false,
          conversation_history: history,
          channel: "website",
        }),
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
            content: accumulated || "Sorry, I couldn't respond. Try again!",
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
            content:
              "Connection issue. Please try again or reach us on WhatsApp.",
            isStreaming: false,
          },
        ];
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, messages]);

  // ── Render ────────────────────────────────────────────────────────

  return (
    <>
      {/* Chat panel */}
      {open && (
        <div
          className="fixed bottom-20 right-4 sm:right-6 z-50 w-[360px] max-w-[calc(100vw-2rem)] h-[500px] max-h-[70vh] flex flex-col rounded-2xl bg-[#0c1f3a] border border-white/10 shadow-2xl shadow-black/40 overflow-hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Chat with Zantara"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#0a1929]">
            <div className="flex items-center gap-2.5">
              <Image
                src="/assets/logo/zantara-lotus.png"
                alt="Zantara"
                width={32}
                height={32}
                className="w-8 h-8"
              />
              <div>
                <p className="text-sm font-medium text-white">Zantara</p>
                <p className="text-[10px] text-white/40">
                  Bali Zero AI Assistant
                </p>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1.5 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`
                    max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed
                    ${
                      msg.role === "user"
                        ? "bg-accent-blue-editorial text-white"
                        : "bg-white/[0.06] text-white/85"
                    }
                    ${msg.isStreaming && !msg.content ? "animate-pulse" : ""}
                  `}
                >
                  {msg.role === "user" ? (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  ) : msg.content ? (
                    <div className="prose prose-invert prose-xs max-w-none prose-p:my-0.5 prose-headings:my-1 prose-ul:my-0.5 prose-li:my-0">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="flex gap-1 py-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce [animation-delay:0ms]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce [animation-delay:150ms]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce [animation-delay:300ms]" />
                    </div>
                  )}
                  {msg.isStreaming && msg.content && (
                    <span className="inline-block w-1 h-3.5 bg-white/40 animate-pulse ml-0.5 align-text-bottom" />
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* WhatsApp CTA after 4+ messages */}
          {messages.filter((m) => m.role === "user").length >= 3 && (
            <div className="px-4 pb-2">
              <a
                href="https://wa.me/628213107363?text=Hi%20Bali%20Zero%2C%20I%20was%20chatting%20with%20Zantara%20on%20your%20website..."
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-[#25D366]/15 text-[#25D366] text-xs font-medium hover:bg-[#25D366]/25 transition-colors"
              >
                <svg
                  className="w-3.5 h-3.5"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                </svg>
                Continue on WhatsApp
              </a>
            </div>
          )}

          {/* Input */}
          <div className="border-t border-white/10 bg-[#0a1929] px-3 py-2.5">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
              className="flex items-center gap-2"
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything..."
                aria-label="Ask anything"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-white/20 transition-colors"
                disabled={isStreaming}
              />
              <button
                type="submit"
                disabled={!input.trim() || isStreaming}
                className="p-2.5 rounded-xl bg-accent-blue-editorial text-white disabled:opacity-30 hover:bg-[#1a41cc] transition-all"
              >
                {isStreaming ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* FAB button */}
      {!open && (
        <button
          onClick={handleOpen}
          className="
            fixed bottom-6 right-6 z-50
            flex items-center gap-2.5 pl-4 pr-5 py-3.5
            rounded-full bg-accent-blue-editorial hover:bg-[#1a41cc]
            shadow-xl shadow-blue-500/25 hover:shadow-blue-500/40
            hover:scale-105 active:scale-100
            transition-all duration-200
            animate-[fadeInUp_0.5s_ease-out_2s_both]
          "
          aria-label="Chat with Zantara"
        >
          <Image
            src="/assets/logo/zantara-lotus.png"
            alt="Zantara"
            width={24}
            height={24}
            className="w-6 h-6"
          />
          <span className="text-white text-sm font-medium">Ask Zantara</span>
        </button>
      )}

      {open && (
        <button
          onClick={() => setOpen(false)}
          className="
            fixed bottom-6 right-6 z-50
            w-12 h-12 rounded-full
            bg-white/10 hover:bg-white/20 backdrop-blur-sm
            shadow-lg shadow-black/20
            flex items-center justify-center
            transition-all duration-200
          "
          aria-label="Close chat"
        >
          <X className="w-5 h-5 text-white" />
        </button>
      )}
    </>
  );
}

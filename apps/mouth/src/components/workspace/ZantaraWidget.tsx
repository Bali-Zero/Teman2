"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { X, Send, Loader2, SquareArrowOutUpRight } from "lucide-react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { sendChat } from "@/lib/gateway";
import { TERMINAL_HANDOFF_KEY } from "@/components/terminal/types";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

interface ZantaraWidgetProps {
  open: boolean;
  onClose: () => void;
}

const genId = () => `z_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

export function ZantaraWidget({ open, onClose }: ZantaraWidgetProps) {
  const pathname = usePathname();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  const send = useCallback(async () => {
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
      const profile = api.getUserProfile();
      const sessionId = profile?.id || "workspace-user";
      const history = messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await sendChat({
        query: text,
        session_id: sessionId,
        conversation_history: history,
        workspace_page: pathname || undefined,
      });

      if (!response || !response.body) throw new Error("No response body");

      const reader = response.body.getReader();
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
            } else if (parsed.type === "terminal_handoff" && parsed.data) {
              try {
                sessionStorage.setItem(
                  TERMINAL_HANDOFF_KEY,
                  JSON.stringify(parsed.data),
                );
              } catch {
                // ignore storage errors
              }
            }
          } catch {
            // skip unparseable lines
          }
        }
      }

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
            content: "Connection issue. Please try again.",
            isStreaming: false,
          },
        ];
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, messages]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[60] bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="fixed top-[10vh] right-0 z-[61] h-[80vh] w-[40vw] min-w-[340px] max-w-[640px] flex flex-col rounded-l-2xl overflow-hidden shadow-2xl"
        style={{
          background: "rgba(10,10,16,0.72)",
          backdropFilter: "blur(28px) saturate(1.4)",
          WebkitBackdropFilter: "blur(28px) saturate(1.4)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRight: "none",
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Zantara AI Assistant"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor: "rgba(255,255,255,0.07)" }}
        >
          <div className="flex items-center gap-3">
            <Image
              src="/static/balizero-logo-clean.png"
              alt="Zantara"
              width={28}
              height={28}
              className="rounded-full"
            />
            <div>
              <p
                className="text-[12px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: "var(--bz-text-1)" }}
              >
                Zantara
              </p>
              <p
                className="text-[9px] uppercase tracking-[0.5px]"
                style={{ color: "var(--bz-text-3)" }}
              >
                AI Assistant · Cmd+J
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/terminal"
              onClick={onClose}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium uppercase tracking-[0.4px] transition-colors hover:bg-white/05"
              style={{ color: "var(--bz-text-3)" }}
            >
              <SquareArrowOutUpRight size={10} />
              <span>Full Terminal</span>
            </Link>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg transition-colors hover:bg-white/05"
              style={{ color: "var(--bz-text-3)" }}
              aria-label="Close Zantara"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <p
                className="text-[12px] font-medium"
                style={{ color: "var(--bz-text-2)" }}
              >
                Ask Zantara anything about clients, cases, regulations…
              </p>
              <p className="text-[10px]" style={{ color: "var(--bz-text-3)" }}>
                Cmd+J to toggle · Esc to close
              </p>
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`
                  max-w-[85%] rounded-2xl px-4 py-3 text-[12.5px] leading-relaxed
                  ${msg.role === "user" ? "" : ""}
                  ${msg.isStreaming && !msg.content ? "animate-pulse" : ""}
                `}
                style={
                  msg.role === "user"
                    ? {
                        background: "var(--bz-accent)",
                        color: "#fff",
                      }
                    : {
                        background: "rgba(255,255,255,0.05)",
                        color: "var(--bz-text-1)",
                        border: "1px solid rgba(255,255,255,0.06)",
                      }
                }
              >
                {msg.role === "user" ? (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                ) : msg.content ? (
                  <div className="prose prose-invert prose-xs max-w-none prose-p:my-0.5 prose-headings:my-1 prose-ul:my-0.5 prose-li:my-0">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="flex gap-1 py-0.5">
                    <span
                      className="w-1.5 h-1.5 rounded-full animate-bounce"
                      style={{
                        background: "var(--bz-text-3)",
                        animationDelay: "0ms",
                      }}
                    />
                    <span
                      className="w-1.5 h-1.5 rounded-full animate-bounce"
                      style={{
                        background: "var(--bz-text-3)",
                        animationDelay: "150ms",
                      }}
                    />
                    <span
                      className="w-1.5 h-1.5 rounded-full animate-bounce"
                      style={{
                        background: "var(--bz-text-3)",
                        animationDelay: "300ms",
                      }}
                    />
                  </div>
                )}
                {msg.isStreaming && msg.content && (
                  <span
                    className="inline-block w-1 h-3.5 animate-pulse ml-0.5 align-text-bottom"
                    style={{ background: "var(--bz-text-3)" }}
                  />
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div
          className="border-t px-4 py-3.5"
          style={{ borderColor: "rgba(255,255,255,0.07)" }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex items-center gap-2.5"
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything…"
              aria-label="Ask Zantara"
              className="flex-1 rounded-xl px-4 py-2.5 text-[12.5px] focus:outline-none transition-all"
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "var(--bz-text-1)",
              }}
              disabled={isStreaming}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="p-2.5 rounded-xl transition-all disabled:opacity-30"
              style={{
                background: "var(--bz-accent)",
                color: "#fff",
              }}
              aria-label="Send message"
            >
              {isStreaming ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

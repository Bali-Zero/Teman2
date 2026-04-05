"use client";

import { useState, useRef, useEffect } from "react";
import type { QuizAnswers, ChatMessage, VisaRecommendation } from "@/lib/visa-oracle/types";
import { sendChatMessage, triggerHandoff } from "@/lib/visa-oracle/api";
import {
  getSession,
  incrementQuestions,
  getRemainingQuestions,
} from "@/lib/visa-oracle/storage";
import { QuestionCounter } from "./QuestionCounter";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { WhatsAppCTA } from "./WhatsAppCTA";

const FALLBACK_WA_URL =
  "https://wa.me/6281338051876?text=Hi%2C%20I%20used%20Visa%20Oracle.";

const INITIAL_SYSTEM_MESSAGE: ChatMessage = {
  role: "system",
  content:
    "I provide information based on current Indonesian immigration data. For your specific situation, our team can give definitive guidance.",
};

interface VisaChatProps {
  quizAnswers?: QuizAnswers;
  initialSessionId?: string;
  visas?: VisaRecommendation[];
}

export function VisaChat({ quizAnswers, initialSessionId, visas }: VisaChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    INITIAL_SYSTEM_MESSAGE,
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [remaining, setRemaining] = useState<number>(() =>
    getRemainingQuestions(),
  );
  const [whatsappUrl, setWhatsappUrl] = useState<string | null>(null);
  const [showCTA, setShowCTA] = useState(false);

  const sessionIdRef = useRef<string>(
    initialSessionId ?? getSession().sessionId,
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function doHandoff(currentMessages: ChatMessage[]) {
    try {
      const response = await triggerHandoff(
        sessionIdRef.current,
        quizAnswers ?? ({} as QuizAnswers),
        visas ?? [],
        currentMessages,
      );
      setWhatsappUrl(response.whatsapp_url ?? FALLBACK_WA_URL);
    } catch {
      setWhatsappUrl(FALLBACK_WA_URL);
    }
    setShowCTA(true);
  }

  async function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    // No questions remaining — trigger handoff immediately
    if (remaining <= 0) {
      if (!whatsappUrl) {
        await doHandoff(messages);
      } else {
        setShowCTA(true);
      }
      return;
    }

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const response = await sendChatMessage(
        sessionIdRef.current,
        trimmed,
        quizAnswers,
        messages,
      );

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.answer,
        confidence: response.confidence,
        sources: response.sources,
      };

      const messagesWithResponse = [...updatedMessages, assistantMessage];
      setMessages(messagesWithResponse);

      // ABSTAIN doesn't count as a question — trigger handoff immediately
      if (response.confidence === "ABSTAIN") {
        await doHandoff(messagesWithResponse);
        return;
      }

      // Increment question count
      incrementQuestions();
      const newRemaining = getRemainingQuestions();
      setRemaining(newRemaining);

      // Used last question — trigger handoff
      if (newRemaining <= 0) {
        await doHandoff(messagesWithResponse);
      }
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: "system",
        content:
          err instanceof Error
            ? `Error: ${err.message}`
            : "Something went wrong. Please try again.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <div
      className="flex flex-col h-[calc(100vh-12rem)] max-h-[700px] rounded-2xl overflow-hidden"
      style={{
        backgroundColor: "var(--bz-elevated)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4 flex-shrink-0"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
      >
        <h2
          className="text-base font-semibold"
          style={{ color: "var(--tx-primary)" }}
        >
          Visa Oracle Chat
        </h2>
        <QuestionCounter remaining={remaining} />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
        {messages.map((msg, idx) => {
          if (msg.role === "system") {
            return (
              <div key={idx} className="flex justify-center">
                <p
                  className="text-xs italic px-4 py-2 rounded-lg max-w-prose text-center"
                  style={{
                    backgroundColor: "var(--bz-surface, rgba(255,255,255,0.04))",
                    color: "var(--tx-secondary)",
                  }}
                >
                  {msg.content}
                </p>
              </div>
            );
          }

          if (msg.role === "user") {
            return (
              <div key={idx} className="flex justify-end">
                <div
                  className="px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[75%] text-sm"
                  style={{
                    backgroundColor: "var(--bz-accent)",
                    color: "#fff",
                  }}
                >
                  {msg.content}
                </div>
              </div>
            );
          }

          // assistant
          return (
            <div key={idx} className="flex justify-start">
              <div
                className="px-4 py-3 rounded-2xl rounded-tl-sm max-w-[80%] text-sm flex flex-col gap-2"
                style={{
                  backgroundColor: "var(--bz-elevated)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "var(--tx-primary)",
                }}
              >
                {msg.confidence && msg.confidence !== "NORMAL" && (
                  <ConfidenceBadge confidence={msg.confidence} />
                )}
                <p className="leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
                {msg.sources && msg.sources.length > 0 && (
                  <div
                    className="text-xs mt-1 flex flex-wrap gap-1"
                    style={{ color: "var(--tx-secondary)" }}
                  >
                    {msg.sources.map((src, si) => (
                      <span
                        key={si}
                        className="px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: "rgba(255,255,255,0.06)",
                        }}
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Loading indicator */}
        {loading && (
          <div className="flex justify-start">
            <div
              className="px-4 py-3 rounded-2xl rounded-tl-sm flex items-center gap-1"
              style={{
                backgroundColor: "var(--bz-elevated)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-2 h-2 rounded-full inline-block"
                  style={{
                    backgroundColor: "var(--tx-secondary)",
                    animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div
        className="flex items-center gap-3 px-5 py-4 flex-shrink-0"
        style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            remaining > 0
              ? "Ask about Indonesian visas..."
              : "No questions remaining"
          }
          disabled={loading || remaining <= 0}
          className="flex-1 rounded-xl px-4 py-2.5 text-sm outline-none transition-colors disabled:opacity-50"
          style={{
            backgroundColor: "var(--bz-base)",
            border: "1px solid rgba(255,255,255,0.12)",
            color: "var(--tx-primary)",
          }}
        />
        <button
          onClick={() => void handleSend()}
          disabled={loading || !input.trim() || remaining <= 0}
          className="px-4 py-2.5 rounded-xl text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-40"
          style={{
            backgroundColor: "var(--bz-accent)",
            color: "#fff",
          }}
        >
          Send
        </button>
      </div>

      {/* Bouncing dots keyframes */}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
      `}</style>

      {/* WhatsApp CTA overlay */}
      {showCTA && whatsappUrl && (
        <WhatsAppCTA
          whatsappUrl={whatsappUrl}
          onDismiss={() => setShowCTA(false)}
        />
      )}
    </div>
  );
}

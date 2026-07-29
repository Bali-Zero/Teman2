"use client";

import React, { useState, useCallback, useRef } from "react";
import {
  MessageCircle,
  Send,
  Loader2,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { STRINGS } from "@/lib/strings";

interface Citation {
  source_id: string;
  cited_text: string;
}

interface OracleResponse {
  answer: string;
  citations: Citation[];
}

interface OracleChatProps {
  clientId: number;
}

const QUICK_PROMPTS = [
  { label: STRINGS.oracle.promptSummarizeProfile, icon: "📋" },
  { label: STRINGS.oracle.promptVisaStatus, icon: "🛂" },
  { label: STRINGS.oracle.promptTaxLkpm, icon: "💰" },
  { label: STRINGS.oracle.promptMissingDocs, icon: "📄" },
] as const;

export function OracleChat({ clientId }: OracleChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<OracleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const submitQuestion = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed || loading) return;

      setLoading(true);
      setError(null);
      setResponse(null);

      try {
        const data = await api.crm.queryClientIntelligence(clientId, trimmed);
        setResponse(data);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        logger.error(`OracleChat query failed for client ${clientId}`, {
          component: "OracleChat",
          itemId: String(clientId),
          reason: msg,
        });
      } finally {
        setLoading(false);
      }
    },
    [clientId, loading],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      submitQuestion(question);
    },
    [question, submitQuestion],
  );

  const handleQuickPrompt = useCallback(
    (prompt: string) => {
      setQuestion(prompt);
      submitQuestion(prompt);
    },
    [submitQuestion],
  );

  return (
    <div
      className="bz-product-panel overflow-hidden"
      style={{
        borderColor:
          "color-mix(in srgb, var(--state-warning) 30%, transparent)",
      }}
    >
      {/* Header — toggle */}
      <button
        onClick={() => {
          setIsOpen((prev) => !prev);
          if (!isOpen) {
            // Focus input on next tick after expanding
            setTimeout(() => inputRef.current?.focus(), 100);
          }
        }}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-[var(--bz-card-hover)]"
      >
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-[var(--state-warning)]" />
          <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
            {STRINGS.oracle.header}
          </h3>
        </div>
        {isOpen ? (
          <ChevronUp className="h-4 w-4 text-[var(--bz-text-2)]" />
        ) : (
          <ChevronDown className="h-4 w-4 text-[var(--bz-text-2)]" />
        )}
      </button>

      {/* Body — collapsible */}
      {isOpen && (
        <div className="border-t border-[var(--bz-border)] px-4 pb-4 pt-3 space-y-3">
          {/* Quick prompts */}
          <div className="flex flex-wrap gap-2">
            {QUICK_PROMPTS.map((qp) => (
              <button
                key={qp.label}
                onClick={() => handleQuickPrompt(qp.label)}
                disabled={loading}
                className="rounded-full border border-[var(--bz-border)] bg-[var(--bz-surface)] px-3 py-1.5 text-xs text-[var(--bz-text-2)] transition-colors hover:border-[var(--state-warning)]/40 hover:bg-[var(--bz-card-hover)] hover:text-[var(--bz-text-1)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="mr-1">{qp.icon}</span>
                {qp.label}
              </button>
            ))}
          </div>

          {/* Free-form input */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={STRINGS.oracle.inputPlaceholder}
              disabled={loading}
              className="flex-1 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] px-3 py-2 text-sm text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-3)] outline-none transition-colors focus:border-[var(--state-warning)]/50 focus:ring-1 focus:ring-[var(--state-warning)]/20 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="flex items-center justify-center rounded-lg border border-[var(--state-warning)]/40 bg-[var(--state-warning)]/10 px-3 py-2 text-[var(--state-warning)] transition-colors hover:bg-[var(--state-warning)]/20 disabled:opacity-40 disabled:cursor-not-allowed"
              title={STRINGS.oracle.sendTitle}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </form>

          {/* Loading state */}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-[var(--bz-text-2)]">
              <Loader2 className="h-4 w-4 animate-spin text-[var(--state-warning)]" />
              <span>{STRINGS.oracle.consulting}</span>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="rounded-lg border border-[var(--state-danger)]/40 bg-[var(--state-danger)]/10 p-3">
              <div className="text-sm font-medium text-[var(--state-danger)]">
                {STRINGS.oracle.requestError}
              </div>
              <div className="mt-1 text-xs text-[var(--state-danger)]/70">
                {error}
              </div>
            </div>
          )}

          {/* Response */}
          {response && (
            <div className="space-y-3">
              {/* Answer text */}
              <div className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-3">
                <p className="text-sm leading-relaxed text-[var(--bz-text-1)] whitespace-pre-wrap">
                  {response.answer}
                </p>
              </div>

              {/* Citations */}
              {response.citations.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--bz-text-2)]">
                    <BookOpen className="h-3 w-3" />
                    <span>
                      {STRINGS.oracle.sourcesLabel} ({response.citations.length}
                      )
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {response.citations.map((cit, idx) => (
                      <span
                        key={`${cit.source_id}-${idx}`}
                        className="inline-flex items-center rounded-full border border-[var(--state-warning)]/30 bg-[var(--state-warning)]/10 px-2.5 py-1 text-[11px] text-[var(--state-warning)]"
                        title={cit.cited_text}
                      >
                        {cit.source_id}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

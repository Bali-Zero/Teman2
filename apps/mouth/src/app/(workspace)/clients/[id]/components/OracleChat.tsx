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
    <div className="rounded-lg border border-amber-500/30 bg-gradient-to-br from-amber-950/10 to-gray-900/40 overflow-hidden">
      {/* Header — toggle */}
      <button
        onClick={() => {
          setIsOpen((prev) => !prev);
          if (!isOpen) {
            // Focus input on next tick after expanding
            setTimeout(() => inputRef.current?.focus(), 100);
          }
        }}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-gray-800/30"
      >
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-gray-100">
            {STRINGS.oracle.header}
          </h3>
        </div>
        {isOpen ? (
          <ChevronUp className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </button>

      {/* Body — collapsible */}
      {isOpen && (
        <div className="border-t border-gray-700/50 px-4 pb-4 pt-3 space-y-3">
          {/* Quick prompts */}
          <div className="flex flex-wrap gap-2">
            {QUICK_PROMPTS.map((qp) => (
              <button
                key={qp.label}
                onClick={() => handleQuickPrompt(qp.label)}
                disabled={loading}
                className="rounded-full border border-gray-700/50 bg-gray-800/40 px-3 py-1.5 text-xs text-gray-300 transition-colors hover:border-amber-500/40 hover:bg-amber-950/20 hover:text-amber-200 disabled:opacity-50 disabled:cursor-not-allowed"
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
              className="flex-1 rounded-lg border border-gray-700/50 bg-gray-900/60 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 outline-none transition-colors focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/20 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="flex items-center justify-center rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-300 transition-colors hover:bg-amber-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
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
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
              <span>{STRINGS.oracle.consulting}</span>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="rounded-lg border border-red-700/40 bg-red-950/20 p-3">
              <div className="text-sm font-medium text-red-400">
                {STRINGS.oracle.requestError}
              </div>
              <div className="mt-1 text-xs text-red-300/70">{error}</div>
            </div>
          )}

          {/* Response */}
          {response && (
            <div className="space-y-3">
              {/* Answer text */}
              <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-3">
                <p className="text-sm leading-relaxed text-gray-200 whitespace-pre-wrap">
                  {response.answer}
                </p>
              </div>

              {/* Citations */}
              {response.citations.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-gray-400">
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
                        className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-950/20 px-2.5 py-1 text-[11px] text-amber-200/80"
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

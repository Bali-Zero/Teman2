'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, Loader2, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface ZantaraChatProps {
  codeContext?: {
    code: string;
    title: string;
    section: string;
  };
  opener?: string;
  suggestions?: string[];
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export function ZantaraChat({ codeContext, opener, suggestions }: ZantaraChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() =>
    typeof window !== 'undefined'
      ? localStorage.getItem('kbli-chat-session') || crypto.randomUUID()
      : ''
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (sessionId && typeof window !== 'undefined') {
      localStorage.setItem('kbli-chat-session', sessionId);
    }
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMsg: ChatMessage = { role: 'user', content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setLoading(true);

      try {
        const contextPrefix = codeContext
          ? `[Context: User is viewing KBLI code ${codeContext.code} — ${codeContext.title}, Section ${codeContext.section}] `
          : '';

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://nuzantara-rag.fly.dev';
        const res = await fetch(`${backendUrl}/api/v1/kbli-notebook/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: contextPrefix + text.trim(),
            session_id: sessionId,
          }),
          signal: AbortSignal.timeout(30000),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const answer =
          data.answer ||
          data.response ||
          "I couldn't find an answer. Try rephrasing your question.";

        setMessages((prev) => [...prev, { role: 'assistant', content: answer }]);
      } catch (err) {
        const errorMsg =
          err instanceof DOMException && err.name === 'TimeoutError'
            ? 'Request timed out. The server might be busy — try again in a moment.'
            : 'Something went wrong. Please try again.';
        setMessages((prev) => [...prev, { role: 'assistant', content: errorMsg }]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading, codeContext, sessionId]
  );

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#1c1c1e]/60 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-all duration-500 hover:shadow-[0_8px_32px_rgba(212,132,90,0.1)] flex flex-col">
      {/* Subtle background glow effect inside the container */}
      <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 rounded-full bg-[#d4845a]/10 blur-[80px] pointer-events-none z-0" />
      <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 rounded-full bg-[#3b82f6]/10 blur-[80px] pointer-events-none z-0" />

      {/* Header */}
      <div className="relative z-10 flex items-center gap-3 border-b border-white/5 bg-white/2 px-5 py-4 backdrop-blur-md">
        <div className="relative flex items-center justify-center w-10 h-10 rounded-full bg-[#d4845a]/10 border border-[#d4845a]/30 shadow-[0_0_15px_rgba(212,132,90,0.2)]">
          <Bot className="h-5 w-5 text-[#d4845a]" />
          <span className="absolute top-0 right-0 w-2.5 h-2.5 bg-green-500 border-2 border-[#1c1c1e] rounded-full animate-pulse-glow" />
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-transparent bg-clip-text bg-linear-to-r from-white to-white/70 tracking-wide">
            Zantara AI
          </span>
          <span className="text-[10px] font-medium text-[#d4845a] uppercase tracking-widest opacity-80">
            OSS Intelligence System
          </span>
        </div>
        {codeContext && (
          <div className="ml-auto flex flex-col items-end">
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Context</span>
            <span className="text-xs font-semibold text-zinc-300 bg-white/5 px-2 py-0.5 rounded-md border border-white/10">
              {codeContext.code}
            </span>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
        className="relative z-10 max-h-96 min-h-[300px] space-y-5 overflow-y-auto p-5 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
      >
        {opener && messages.length === 0 && (
          <div className="flex animate-fade-in-up">
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white/5 border border-white/5 shadow-sm px-4 py-3">
              <div className="text-sm leading-relaxed text-zinc-300">{opener}</div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex animate-fade-in-up ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            style={{ animationDelay: `${Math.min(i * 50, 300)}ms` }}
          >
            {msg.role === 'assistant' && (
              <div className="shrink-0 mr-3 mt-1">
                <div className="flex items-center justify-center w-6 h-6 rounded-full bg-white/5 border border-white/10">
                  <Bot className="h-3 w-3 text-zinc-400" />
                </div>
              </div>
            )}

            <div
              className={
                msg.role === 'user'
                  ? 'max-w-[80%] rounded-2xl rounded-tr-sm bg-linear-to-br from-[#d4845a]/20 to-[#d4845a]/5 border border-[#d4845a]/30 shadow-[0_4px_20px_rgba(212,132,90,0.1)] px-4 py-3 text-sm text-white font-medium'
                  : 'max-w-[85%] rounded-2xl rounded-tl-sm bg-white/5 border border-white/5 border-l-2 border-l-[#3b82f6]/50 shadow-sm px-4 py-3 prose prose-invert prose-sm prose-p:leading-relaxed prose-p:text-zinc-300 prose-a:text-[#d4845a] prose-strong:text-white'
              }
            >
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start animate-fade-in-up">
            <div className="shrink-0 mr-3 mt-1">
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-[#d4845a]/20 border border-[#d4845a]/30 shadow-[0_0_10px_rgba(212,132,90,0.2)]">
                <Loader2 className="h-3 w-3 text-[#d4845a] animate-spin" />
              </div>
            </div>
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-transparent px-2 py-3">
              <div className="flex space-x-1">
                <div
                  className="w-1.5 h-1.5 bg-[#d4845a]/60 rounded-full animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <div
                  className="w-1.5 h-1.5 bg-[#d4845a]/60 rounded-full animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <div
                  className="w-1.5 h-1.5 bg-[#d4845a]/60 rounded-full animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion chips */}
      {suggestions && suggestions.length > 0 && messages.length === 0 && (
        <div className="relative z-10 flex flex-wrap gap-2 px-5 pb-3">
          {suggestions.map((s, idx) => (
            <button
              key={s}
              type="button"
              onClick={() => sendMessage(s)}
              aria-label={`Ask: ${s}`}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-zinc-400
                         transition-all duration-300 hover:bg-[#d4845a]/10 hover:border-[#d4845a]/40 hover:text-[#d4845a] hover:shadow-[0_0_15px_rgba(212,132,90,0.2)] hover:-translate-y-0.5 animate-fade-in-up"
              style={{ animationDelay: `${(idx + 1) * 100}ms` }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input Area */}
      <div className="relative z-10 p-4 border-t border-white/5 bg-black/20">
        <div className="relative flex items-end gap-2 rounded-xl border border-white/10 bg-white/5 p-1 transition-all focus-within:border-[#d4845a]/40 focus-within:bg-[#1c1c1e] focus-within:shadow-[0_0_20px_rgba(212,132,90,0.15)]">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
              if (e.key === 'Escape') {
                setInput('');
                inputRef.current?.blur();
              }
            }}
            placeholder={
              codeContext
                ? `Ask about ${codeContext.code}...`
                : 'Ask Zantara anything about KBLI...'
            }
            rows={1}
            className="flex-1 max-h-32 min-h-[44px] resize-none bg-transparent px-3 py-3 text-sm text-white placeholder-zinc-500 outline-none scrollbar-thin"
            aria-label="Chat with Zantara AI"
          />
          <button
            type="button"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="shrink-0 mb-1 mr-1 flex h-9 w-9 items-center justify-center rounded-lg bg-linear-to-br from-[#d4845a] to-[#b36a46] text-white shadow-md transition-all disabled:opacity-30 disabled:grayscale hover:shadow-[0_0_15px_rgba(212,132,90,0.4)] hover:scale-105 active:scale-95"
            aria-label="Send message"
          >
            <Send className="h-4 w-4 ml-0.5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}

'use client';

import * as React from 'react';
import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageCircle,
  Send,
  Loader2,
  Sparkles,
  ChevronDown,
  ExternalLink,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface ScriptedQA {
  /** The question */
  q: string;
  /** The pre-written answer */
  a: string;
  /** Optional sources to display */
  sources?: { title: string; url: string }[];
}

export interface AskZantaraProps {
  /** Context for the AI (article topic, category, etc.) */
  context?: string;
  /** Placeholder text */
  placeholder?: string;
  /** Suggested questions (for AI mode) */
  suggestedQuestions?: string[];
  /** Pre-scripted Q&A pairs (no API calls, fully controlled) */
  scripted?: ScriptedQA[];
  /** API endpoint for asking questions */
  apiEndpoint?: string;
  /** Custom class */
  className?: string;
  /** Variant */
  variant?: 'inline' | 'floating' | 'sidebar';
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: { title: string; url: string }[];
  timestamp: Date;
}

// ============================================================================
// Main Component
// ============================================================================

export function AskZantara({
  context,
  placeholder = 'Ask a question about this topic...',
  suggestedQuestions = [],
  scripted,
  apiEndpoint = '/api/blog/ask',
  className,
  variant = 'inline',
}: AskZantaraProps) {
  const [isOpen, setIsOpen] = useState(variant !== 'floating');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);

  // Check if we're in scripted mode
  const isScriptedMode = scripted && scripted.length > 0;

  // Handle scripted question click
  const handleScriptedQuestion = useCallback((qa: ScriptedQA) => {
    if (isLoading) return;

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: qa.q,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setShowSuggestions(false);
    setIsLoading(true);

    // Simulate "thinking" delay (200-500ms for realism)
    const delay = 200 + Math.random() * 300;
    setTimeout(() => {
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: qa.a,
        sources: qa.sources,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, delay);
  }, [isLoading]);

  // Handle sending a question (AI mode)
  const handleSend = useCallback(async (question?: string) => {
    const q = question || input.trim();
    if (!q || isLoading) return;

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: q,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setShowSuggestions(false);
    setIsLoading(true);

    try {
      // Call API
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, context }),
      });

      if (!response.ok) throw new Error('Failed to get response');

      const data = await response.json();

      // Add assistant message
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.answer || "I couldn't find an answer to that question.",
        sources: data.sources,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      // Add error message
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: "Sorry, I couldn't process your question. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, apiEndpoint, context]);

  // Handle keyboard submit
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Floating variant
  if (variant === 'floating') {
    return (
      <>
        {/* Floating button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            'fixed bottom-6 right-6 z-50 p-4 rounded-full shadow-lg',
            'bg-gradient-to-r from-[#2251ff] to-[#4d73ff]',
            'text-white hover:scale-105 transition-transform'
          )}
        >
          <MessageCircle className="w-6 h-6" />
        </button>

        {/* Floating panel */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="fixed bottom-24 right-6 z-50 w-96 max-h-[500px] bg-black/95 rounded-2xl border border-white/10 shadow-2xl overflow-hidden"
            >
              <AskZantaraContent
                messages={messages}
                input={input}
                setInput={setInput}
                isLoading={isLoading}
                showSuggestions={showSuggestions}
                suggestedQuestions={suggestedQuestions}
                scripted={scripted}
                isScriptedMode={isScriptedMode}
                onScriptedQuestion={handleScriptedQuestion}
                placeholder={placeholder}
                onSend={handleSend}
                onKeyDown={handleKeyDown}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </>
    );
  }

  // Inline or sidebar variant
  return (
    <div className={cn(
      'bg-black/40 rounded-2xl border border-white/10 overflow-hidden',
      variant === 'sidebar' && 'sticky top-4',
      className
    )}>
      <AskZantaraContent
        messages={messages}
        input={input}
        setInput={setInput}
        isLoading={isLoading}
        showSuggestions={showSuggestions}
        suggestedQuestions={suggestedQuestions}
        scripted={scripted}
        isScriptedMode={isScriptedMode}
        onScriptedQuestion={handleScriptedQuestion}
        placeholder={placeholder}
        onSend={handleSend}
        onKeyDown={handleKeyDown}
      />
    </div>
  );
}

// ============================================================================
// Content Component
// ============================================================================

function AskZantaraContent({
  messages,
  input,
  setInput,
  isLoading,
  showSuggestions,
  suggestedQuestions,
  scripted,
  isScriptedMode,
  onScriptedQuestion,
  placeholder,
  onSend,
  onKeyDown,
}: {
  messages: Message[];
  input: string;
  setInput: (v: string) => void;
  isLoading: boolean;
  showSuggestions: boolean;
  suggestedQuestions: string[];
  scripted?: ScriptedQA[];
  isScriptedMode?: boolean;
  onScriptedQuestion?: (qa: ScriptedQA) => void;
  placeholder: string;
  onSend: (q?: string) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
}) {
  // Get questions that haven't been asked yet (for scripted mode)
  const askedQuestions = new Set(
    messages.filter((m) => m.role === 'user').map((m) => m.content)
  );
  const remainingScriptedQuestions = scripted?.filter((qa) => !askedQuestions.has(qa.q)) || [];
  return (
    <>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 bg-gradient-to-r from-[#2251ff]/10 to-transparent">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-[#2251ff]/20">
            <Sparkles className="w-4 h-4 text-[#2251ff]" />
          </div>
          <div>
            <h4 className="font-medium text-white text-sm">Ask Zantara</h4>
            <p className="text-white/40 text-xs">AI-powered answers from our knowledge base</p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="max-h-[300px] overflow-y-auto p-4 space-y-4">
        {/* Scripted mode: show remaining questions */}
        {isScriptedMode && remainingScriptedQuestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-white/40 text-xs">
              {messages.length === 0 ? 'Ask me about:' : 'More questions:'}
            </p>
            {remainingScriptedQuestions.map((qa, i) => (
              <button
                key={i}
                onClick={() => onScriptedQuestion?.(qa)}
                disabled={isLoading}
                className={cn(
                  'w-full text-left p-3 rounded-lg border text-sm transition-colors',
                  'bg-white/5 hover:bg-white/10 border-white/10',
                  'text-white/70 hover:text-white',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {qa.q}
              </button>
            ))}
          </div>
        )}

        {/* AI mode: show suggested questions */}
        {!isScriptedMode && messages.length === 0 && showSuggestions && suggestedQuestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-white/40 text-xs">Suggested questions:</p>
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => onSend(q)}
                className="w-full text-left p-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-white/70 hover:text-white transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'flex',
              message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'max-w-[85%] p-3 rounded-xl text-sm',
                message.role === 'user'
                  ? 'bg-[#2251ff] text-white'
                  : 'bg-white/10 text-white/80'
              )}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>

              {/* Sources */}
              {message.sources && message.sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-white/10">
                  <p className="text-xs text-white/40 mb-1">Sources:</p>
                  {message.sources.map((source, i) => (
                    <a
                      key={i}
                      href={source.url}
                      className="flex items-center gap-1 text-xs text-[#2251ff] hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                      {source.title}
                    </a>
                  ))}
                </div>
              )}

              {/* Feedback buttons for assistant messages */}
              {message.role === 'assistant' && (
                <div className="flex items-center gap-2 mt-2 pt-2 border-t border-white/10">
                  <button className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-emerald-400 transition-colors">
                    <ThumbsUp className="w-3 h-3" />
                  </button>
                  <button className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-red-400 transition-colors">
                    <ThumbsDown className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white/10 p-3 rounded-xl">
              <Loader2 className="w-4 h-4 text-white/60 animate-spin" />
            </div>
          </div>
        )}
      </div>

      {/* Input - only show in AI mode or when all scripted questions are exhausted */}
      {!isScriptedMode ? (
        <div className="p-4 border-t border-white/10">
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={placeholder}
              disabled={isLoading}
              className={cn(
                'w-full px-4 py-2.5 pr-12 rounded-xl',
                'bg-white/5 border border-white/10',
                'text-white placeholder:text-white/30',
                'focus:outline-none focus:border-[#2251ff]/50 focus:ring-1 focus:ring-[#2251ff]/20',
                'transition-colors disabled:opacity-50'
              )}
            />
            <button
              onClick={() => onSend()}
              disabled={!input.trim() || isLoading}
              className={cn(
                'absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg',
                'text-white/40 hover:text-[#2251ff] hover:bg-[#2251ff]/10',
                'transition-colors disabled:opacity-30 disabled:cursor-not-allowed'
              )}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : remainingScriptedQuestions.length === 0 && messages.length > 0 ? (
        // All questions answered in scripted mode
        <div className="p-4 border-t border-white/10">
          <p className="text-center text-white/40 text-sm">
            All questions answered! Need more help? Contact us.
          </p>
        </div>
      ) : null}
    </>
  );
}

'use client';

import React, { useState, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  User,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  Shield,
  Zap,
  Clock,
  Database,
  Sparkles,
  HeartHandshake,
  HelpCircle,
  BookOpen,
  Lightbulb,
  Brain,
  Star,
  MessageSquarePlus,
} from 'lucide-react';
import { CitationCard } from '@/components/search/CitationCard';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';

import { formatMessageTime } from '@/lib/utils';
import { Message } from '@/types';
import { PricingTable } from './PricingTable';
import { PricingResponse } from '@/types/pricing';
import { TIMEOUTS, ANIMATION } from '@/constants';

interface MessageBubbleProps {
  message: Message;
  userAvatar?: string | null;
  isLast?: boolean;
  onFollowUpClick?: (question: string) => void;
}

const VerificationBadge = ({ score }: { score: number }) => {
  let colorClass = 'text-[var(--error)] border-[var(--error)]/30 bg-[var(--error)]/10';
  let icon = <ShieldAlert className="w-3 h-3" />;
  let label = 'Low Confidence';

  if (score >= 80) {
    colorClass = 'text-[var(--success)] border-[var(--success)]/30 bg-[var(--success)]/10';
    icon = <ShieldCheck className="w-3 h-3" />;
    label = 'Verified';
  } else if (score >= 50) {
    colorClass = 'text-[var(--warning)] border-[var(--warning)]/30 bg-[var(--warning)]/10';
    icon = <Shield className="w-3 h-3" />;
    label = 'Medium Confidence';
  }

  return (
    <div
      className={`
      inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
      text-[10px] font-medium border ${colorClass}
      mt-2 select-none
    `}
    >
      {icon}
      <span>
        {label} ({score}%)
      </span>
    </div>
  );
};

const TrustHeader = ({ metadata }: { metadata: NonNullable<Message['metadata']> }) => {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[10px] font-medium text-[var(--foreground-muted)] mb-3 select-none">
      {metadata.route_used && (
        <div className="flex items-center gap-1 bg-[var(--background-secondary)] px-1.5 py-0.5 rounded border border-[var(--border)]">
          <Zap
            size={10}
            className={metadata.route_used.includes('deep') ? 'text-purple-400' : 'text-blue-400'}
          />
          <span>
            {metadata.route_used.toLowerCase().includes('fast')
              ? 'FAST'
              : metadata.route_used.toLowerCase().includes('pro')
                ? 'PRO'
                : metadata.route_used.toLowerCase().includes('deep')
                  ? 'DEEP'
                  : metadata.route_used.toUpperCase()}
          </span>
        </div>
      )}
      {metadata.execution_time && (
        <div className="flex items-center gap-1 px-1.5 py-0.5">
          <Clock size={10} />
          <span>{metadata.execution_time.toFixed(1)}s</span>
        </div>
      )}
      {metadata.context_length && (
        <div className="flex items-center gap-1 px-1.5 py-0.5">
          <Database size={10} />
          <span>{Math.round(metadata.context_length / 100) / 10}k ctx</span>
        </div>
      )}
    </div>
  );
};

const EmotionalBadge = ({ emotion }: { emotion: string }) => {
  if (emotion === 'NEUTRAL') return null;

  // Map emotions to colors/icons
  const config: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
    URGENT: {
      color: 'text-red-400 bg-red-400/10 border-red-400/20',
      icon: <Zap size={12} />,
      label: 'Priority Mode',
    },
    CONFUSED: {
      color: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
      icon: <HelpCircle size={12} />,
      label: 'Simplified Explanation',
    }, // BreastCheck is not a valid icon, using HelpCircle like or similar
    STRESSED: {
      color: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
      icon: <HeartHandshake size={12} />,
      label: 'Supportive Tone',
    },
    EXCITED: {
      color: 'text-green-400 bg-green-400/10 border-green-400/20',
      icon: <Sparkles size={12} />,
      label: 'Enthusiastic',
    },
  };

  const defaultConf = {
    color: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
    icon: <Sparkles size={12} />,
    label: emotion,
  };
  const { color, icon, label } = config[emotion] || defaultConf;

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-semibold border ${color} mb-2`}
    >
      {icon}
      <span>{label}</span>
    </div>
  );
};

function MessageBubbleComponent({ message, userAvatar, isLast, onFollowUpClick }: MessageBubbleProps) {
  const { role, content, sources, imageUrl, timestamp, steps, verification_score } = message;
  const isUser = role === 'user';
  const [copied, setCopied] = useState(false);
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);
  const copyTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Typewriter Effect State
  const [displayedContent, setDisplayedContent] = useState(content);

  React.useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  React.useEffect(() => {
    // Only animate if:
    // 1. It's the last message
    // 2. It's from assistant
    // 3. It's new (less than 10 seconds old) to avoid animating history on reload
    // 4. Content is available
    const isRecent = (Date.now() - timestamp.getTime()) < 10000;
    const shouldAnimate = isLast && !isUser && isRecent && content;

    if (shouldAnimate) {
      setDisplayedContent('');
      let currentIndex = 0;
      const text = content;
      let animationFrameId: number;
      
      const typeChar = () => {
        if (currentIndex < text.length) {
          // Dynamic speed: faster for longer texts, slower for short ones
          // Base: 2 chars per frame (at 60fps = 120 chars/sec)
          // Long text (>500 chars): 5 chars per frame (300 chars/sec)
          const charsPerFrame = text.length > 500 ? 5 : 2;
          
          currentIndex += charsPerFrame;
          if (currentIndex > text.length) currentIndex = text.length;
          
          setDisplayedContent(text.slice(0, currentIndex));
          animationFrameId = requestAnimationFrame(typeChar);
        } else {
          setDisplayedContent(text);
        }
      };
      
      animationFrameId = requestAnimationFrame(typeChar);
      
      return () => cancelAnimationFrame(animationFrameId);
    } else {
      setDisplayedContent(content);
    }
  }, [content, isLast, isUser, timestamp]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    if (copyTimeoutRef.current) {
      clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = setTimeout(() => {
      setCopied(false);
      copyTimeoutRef.current = null;
    }, TIMEOUTS.COPY_FEEDBACK);
  };

  // Function to extract pricing data from tool steps
  const getPricingData = (): PricingResponse | null => {
    if (!message.steps) return null;

    // Look for get_pricing tool output in steps
    // We reverse to get the latest one if multiple exist
    const toolStep = [...message.steps]
      .reverse()
      .find(
        (step) =>
          step.type === 'tool_end' &&
          step.data.result &&
          (step.data.result.includes('official_notice') ||
            step.data.result.includes('single_entry_visas'))
      );

    if (toolStep && toolStep.type === 'tool_end') {
      try {
        const data = JSON.parse(toolStep.data.result);
        if (data.success && data.data) {
          return data.data as PricingResponse;
        }
        // Handle cases where result is directly the data or wrapped differently
        if (data.official_notice || data.single_entry_visas) {
          return data as PricingResponse;
        }
      } catch {
        // Failed to parse, ignore
      }
    }
    return null;
  };

  const pricingData = getPricingData();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: ANIMATION.FRAMER_DEFAULT, ease: 'easeOut' }}
      className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6 group`}
    >
      <div
        className={`flex max-w-[85%] md:max-w-[75%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      >
        {/* Avatar */}
        <div
          className={`
          flex-shrink-0 flex items-center justify-center
          ${
            isUser
              ? 'w-10 h-10 rounded-full shadow-lg bg-[var(--background-secondary)] text-[var(--foreground)]' // Larger (25%), no border
              : 'w-14 h-14 -ml-2 bg-transparent border-0 shadow-none' // PURE LOGO. NO CONTAINER.
          }
        `}
        >
          {isUser ? (
            userAvatar ? (
              <div className="relative w-full h-full rounded-full overflow-hidden">
                <Image src={userAvatar} alt="User" fill className="object-cover" />
              </div>
            ) : (
              <User size={16} />
            )
          ) : (
            <div className="relative w-full h-full"> 
              <Image 
                src="/assets/logo/logo_zan.png" 
                alt="Zantara" 
                fill 
                className="object-contain brightness-110 drop-shadow-[0_0_15px_rgba(100,100,255,0.4)] scale-125" 
              />
            </div>
          )}
        </div>

        {/* Message Content */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} min-w-0`}>
          <div
            className={`
            relative px-5 py-3.5 rounded-2xl shadow-sm text-sm leading-relaxed overflow-hidden
            ${
              isUser
                ? 'bg-[var(--background-secondary)] text-[var(--foreground)] rounded-tr-sm'
                : 'bg-[var(--background-elevated)] text-[var(--foreground)] rounded-tl-sm border border-[var(--border)]/50'
            }
          `}
          >
            {/* Trust Header & Emotional Badge */}
            {!isUser && message.metadata && (
              <div className="flex flex-col gap-2 mb-3">
                <TrustHeader metadata={message.metadata} />
                
                {/* Memory & Context Indicators */}
                <div className="flex flex-wrap gap-2">
                  {message.metadata.golden_answer_used && (
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <Star size={10} className="fill-current" />
                      <span>Golden Answer</span>
                    </div>
                  )}
                  
                  {(message.metadata.user_memory_facts?.length ?? 0) > 0 && (
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" title={`${message.metadata.user_memory_facts?.length} personal facts used`}>
                      <User size={10} />
                      <span>Personalized</span>
                    </div>
                  )}

                  {(message.metadata.collective_memory_facts?.length ?? 0) > 0 && (
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-teal-500/10 text-teal-400 border border-teal-500/20" title={`${message.metadata.collective_memory_facts?.length} collective facts used`}>
                      <Brain size={10} />
                      <span>Collective Wisdom</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            {!isUser && message.metadata?.emotional_state && (
              <EmotionalBadge emotion={message.metadata.emotional_state} />
            )}

            {/* Thinking Process (for AI) */}
            {!isUser && (steps?.length ?? 0) > 0 && (
              <div className="mb-3">
                <button
                  onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
                  className="flex items-center gap-2 text-xs font-medium text-[var(--foreground-muted)] hover:text-[var(--accent)] transition-colors mb-2"
                >
                  <Lightbulb className="w-3.5 h-3.5" />
                  <span>Thinking Process</span>
                  {isThinkingExpanded ? (
                    <ChevronDown className="w-3 h-3" />
                  ) : (
                    <ChevronRight className="w-3 h-3" />
                  )}
                </button>

                <AnimatePresence>
                  {isThinkingExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pl-3 border-l-2 border-[var(--border)] space-y-2 py-1">
                        {steps?.map((step, idx) => (
                          <div key={idx} className="text-xs text-[var(--foreground-secondary)]">
                            <span className="opacity-70 mr-1">{idx + 1}.</span>
                            {step.type === 'status' && <span>{step.data}</span>}

                            {/* STANDARD TOOLS */}
                            {step.type === 'tool_start' && step.data.name !== 'database_query' && (
                              <span className="text-blue-400">
                                Using tool: <strong>{step.data.name}</strong>
                              </span>
                            )}

                            {/* DEEP DIVE (DATABASE QUERY) - SPECIAL RENDERING */}
                            {step.type === 'tool_start' && step.data.name === 'database_query' && (
                              <span className="text-indigo-400 flex items-center gap-1.5 font-medium">
                                <BookOpen size={12} />
                                <span>Deep Reading Document...</span>
                              </span>
                            )}

                            {step.type === 'tool_end' && (
                              <span className="text-emerald-400">Tool Completed</span>
                            )}

                            {/* Reasoning Steps */}
                            {step.type === 'reasoning_step' && (
                              <div className="flex flex-col gap-1 mt-1 mb-2">
                                <div className="flex items-center gap-1.5 font-medium">
                                  <Sparkles size={12} className="text-purple-400" />
                                  <span className="text-purple-400">
                                    {step.data.phase ? `${step.data.phase.charAt(0).toUpperCase() + step.data.phase.slice(1)}: ` : ''}{step.data.status}
                                  </span>
                                </div>
                                {step.data.message && (
                                  <span className="text-[10px] text-[var(--foreground-muted)] ml-4 italic">
                                    "{step.data.message}"
                                  </span>
                                )}
                                {/* Show details if available (e.g. corrections count) */}
                                {step.data.details && (
                                  <div className="ml-4 text-[10px]">
                                    {(() => {
                                      const details = step.data.details as { corrections?: unknown[] };
                                      if (details.corrections && Array.isArray(details.corrections) && details.corrections.length > 0) {
                                        return (
                                          <div className="text-[var(--warning)] flex items-center gap-1">
                                            <ShieldAlert size={10} />
                                            {details.corrections.length} Corrections Applied
                                          </div>
                                        );
                                      }
                                      return null;
                                    })()}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {/* Main Text Content */}
            <div className="prose prose-invert prose-sm max-w-none break-words">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayedContent}</ReactMarkdown>
            </div>

            {/* Verification Badge */}
            {!isUser && verification_score !== undefined && (
              <VerificationBadge score={verification_score} />
            )}

            {/* Pricing Table */}
            {!isUser && pricingData && <PricingTable data={pricingData} />}

            {/* Sources */}
            {!isUser && sources && sources.length > 0 && <CitationCard sources={sources} />}

            {/* Follow-up Questions */}
            {!isUser && message.metadata?.followup_questions && message.metadata.followup_questions.length > 0 && (
              <div className="mt-4 pt-3 border-t border-[var(--border)]/50">
                <p className="text-[10px] font-medium text-[var(--foreground-muted)] mb-2 flex items-center gap-1.5">
                  <MessageSquarePlus size={12} />
                  SUGGESTED FOLLOW-UPS
                </p>
                <div className="flex flex-wrap gap-2">
                  {message.metadata.followup_questions.map((question, idx) => (
                    <button
                      key={idx}
                      onClick={() => onFollowUpClick?.(question)}
                      className="text-xs text-left px-3 py-1.5 rounded-lg bg-[var(--background-secondary)] hover:bg-[var(--accent)]/10 hover:text-[var(--accent)] border border-[var(--border)] transition-colors duration-200"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Image */}
            {imageUrl && (
              <div className="mt-3 relative rounded-lg overflow-hidden border border-[var(--border)]">
                <Image
                  src={imageUrl}
                  alt="Generated content"
                  width={512}
                  height={512}
                  className="w-full h-auto"
                  unoptimized
                />
              </div>
            )}
          </div>

          {/* Footer Metadata */}
          <div className="flex items-center gap-2 mt-1 px-1">
            <span className="text-[10px] text-[var(--foreground-muted)]">
              {formatMessageTime(timestamp)}
            </span>
            <button
              onClick={handleCopy}
              className="transition-opacity p-1 hover:bg-[var(--background-secondary)] rounded opacity-70 hover:opacity-100"
              aria-label="Copy message"
            >
              {copied ? (
                <Check className="w-3 h-3 text-[var(--success)]" />
              ) : (
                <Copy className="w-3 h-3 text-[var(--foreground-muted)]" />
              )}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export const MessageBubble = memo(MessageBubbleComponent);
